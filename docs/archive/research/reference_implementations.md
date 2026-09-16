# Football Video Analysis: Reference Implementations & Integration Guide

This document distills the best patterns extracted from 8 open-source football tracking repositories. It provides concrete code snippets and architectural blueprints that can be directly implemented into our `run_guerilla.py` backend without needing to reference the original repositories again.

---

## 1. Modular Architecture & Caching (The Orchestrator Pattern)

**Why borrow:** The current `run_guerilla.py` is monolithic. The reference repositories use an orchestrator `main.py` that passes a central `tracks` dictionary through specialized classes. Crucially, they use `.pkl` (pickle) caching ("stubs") so that slow GPU inference (YOLO + tracking) only runs once during development.

**Implementation Blueprint (`main.py` equivalent):**

```python
import pickle
import os

def main():
    video_frames = read_video('input_videos/match.mp4')
    
    # 1. Detection & Tracking (with caching)
    tracker = Tracker('models/yolov10n.pt')
    tracks = tracker.get_object_tracks(
        video_frames, 
        read_from_stub=True, 
        stub_path='stubs/track_stubs.pkl'
    )
    
    # 2. Camera Movement Compensation
    camera_estimator = CameraMovementEstimator(video_frames[0])
    camera_movement = camera_estimator.get_camera_movement(
        video_frames,
        read_from_stub=True,
        stub_path='stubs/camera_movement_stub.pkl'
    )
    camera_estimator.add_adjust_positions_to_tracks(tracks, camera_movement)
    
    # 3. Perspective Transform (Pixels -> Meters)
    view_transformer = ViewTransformer()
    view_transformer.add_transformed_position_to_tracks(tracks)
    
    # 4. Team Assignment
    team_assigner = TeamAssigner()
    team_assigner.assign_team_color(video_frames[0], tracks['players'][0])
    # ... loop through frames to assign teams
    
    # 5. Output JSON for Frontend (TacticalPitch.tsx)
    export_tracks_to_json(tracks, 'output/match_data.json')
```

---

## 2. Camera Movement Estimation (Optical Flow)

**Why borrow:** Broadcast cameras pan and zoom constantly. If we don't subtract the camera's movement from the players' pixel movement, speed and distance calculations will be wildly inaccurate.

**How it works:** We use OpenCV's Lucas-Kanade optical flow (`cv2.calcOpticalFlowPyrLK`) to track features in the background (e.g., the crowd or stadium roof, avoiding the pitch) between frames. 

**Code Snippet (`camera_movement_estimator.py`):**

```python
import cv2
import numpy as np

class CameraMovementEstimator:
    def __init__(self, first_frame):
        self.minimum_distance = 5
        self.lk_params = dict(
            winSize=(15, 15),
            maxLevel=2,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03)
        )
        
        # Mask out the pitch to only track the background (e.g., stadium seating)
        gray = cv2.cvtColor(first_frame, cv2.COLOR_BGR2GRAY)
        mask = np.zeros_like(gray)
        mask[:, 0:20] = 1       # Track left edge
        mask[:, 900:1050] = 1   # Track right/bottom edge (adjust based on video res)
        
        self.features_params = dict(maxCorners=100, qualityLevel=0.3, minDistance=3, blockSize=7, mask=mask)

    def get_camera_movement(self, frames):
        camera_movement = [[0, 0]] * len(frames)
        old_gray = cv2.cvtColor(frames[0], cv2.COLOR_BGR2GRAY)
        old_features = cv2.goodFeaturesToTrack(old_gray, **self.features_params)

        for i in range(1, len(frames)):
            frame_gray = cv2.cvtColor(frames[i], cv2.COLOR_BGR2GRAY)
            new_features, status, error = cv2.calcOpticalFlowPyrLK(old_gray, frame_gray, old_features, None, **self.lk_params)
            
            max_distance = 0
            cam_x, cam_y = 0, 0
            
            # Find the strongest background movement
            for (new, old) in zip(new_features, old_features):
                new_pt, old_pt = new.ravel(), old.ravel()
                dist = np.linalg.norm(new_pt - old_pt)
                if dist > max_distance:
                    max_distance = dist
                    cam_x, cam_y = new_pt[0] - old_pt[0], new_pt[1] - old_pt[1]
            
            if max_distance > self.minimum_distance:
                camera_movement[i] = [cam_x, cam_y]
                # Re-acquire features if movement was significant
                old_features = cv2.goodFeaturesToTrack(frame_gray, **self.features_params)
                
            old_gray = frame_gray.copy()
            
        return camera_movement

    def add_adjust_positions_to_tracks(self, tracks, camera_movement):
        for object_type, object_tracks in tracks.items():
            for frame_num, track_frame in enumerate(object_tracks):
                for track_id, info in track_frame.items():
                    pos = info['position']
                    cam_mov = camera_movement[frame_num]
                    # Subtract camera movement from player's raw pixel position
                    tracks[object_type][frame_num][track_id]['position_adjusted'] = (
                        pos[0] - cam_mov[0], 
                        pos[1] - cam_mov[1]
                    )
```

---

## 3. Perspective Transformation (Homography)

**Why borrow:** We must map 2D video pixels (camera view) to a top-down tactical 2D map in meters (e.g., 105m x 68m) for the frontend (`TacticalPitch.tsx`).

**How it works:** We define 4 reference points on the video (e.g., the corners of the penalty box) and map them to their known real-world physical coordinates. We use `cv2.getPerspectiveTransform`.

**Code Snippet (`view_transformer.py`):**

```python
import cv2
import numpy as np

class ViewTransformer:
    def __init__(self):
        # Real-world pitch dimensions in meters (example: penalty box area)
        court_width = 68
        court_length = 23.32

        # 1. The 4 points selected from the specific video frame (pixels)
        # TODO: Make this dynamic or user-selectable via frontend
        self.pixel_vertices = np.array([
            [110, 1035], 
            [265, 275], 
            [910, 260], 
            [1640, 915]
        ], dtype=np.float32)
        
        # 2. The corresponding 4 points on a real-world top-down map (meters)
        self.target_vertices = np.array([
            [0, court_width],
            [0, 0],
            [court_length, 0],
            [court_length, court_width]
        ], dtype=np.float32)

        # Calculate the transformation matrix
        self.matrix = cv2.getPerspectiveTransform(self.pixel_vertices, self.target_vertices)

    def transform_point(self, point):
        # Check if the player is actually inside the defined polygon
        is_inside = cv2.pointPolygonTest(self.pixel_vertices, (int(point[0]), int(point[1])), False) >= 0 
        if not is_inside:
            return None

        # Apply matrix to the point
        reshaped_point = np.array(point).reshape(-1, 1, 2).astype(np.float32)
        transformed = cv2.perspectiveTransform(reshaped_point, self.matrix)
        return transformed.squeeze().tolist()

    def add_transformed_position_to_tracks(self, tracks):
        for object_type, object_tracks in tracks.items():
            for frame_num, track_frame in enumerate(object_tracks):
                for track_id, info in track_frame.items():
                    pos = info.get('position_adjusted')
                    if pos:
                        tracks[object_type][frame_num][track_id]['position_transformed'] = self.transform_point(pos)
```

---

## 4. Team Assignment via K-Means Clustering

**Why borrow:** It requires zero training data. It dynamically clusters player jersey colors into two groups based on the dominant colors found in the top half of their bounding boxes.

**How it works:** Crop the player, take the top 50% (jersey), convert to HSV, and use `sklearn.cluster.KMeans(n_clusters=2)`.

**Code Snippet (`team_assigner.py`):**

```python
import cv2
import numpy as np
from sklearn.cluster import KMeans

class TeamAssigner:
    def __init__(self):
        self.team_colors = {}
        self.kmeans = None

    def get_player_color(self, frame, bbox):
        # Crop player from frame
        image = frame[int(bbox[1]):int(bbox[3]), int(bbox[0]):int(bbox[2])]
        
        # Take only the top half of the crop (jersey) to ignore shorts/socks/grass
        top_half = image[0:int(image.shape[0] / 2), :]
        
        # Convert to HSV and flatten
        top_half_hsv = cv2.cvtColor(top_half, cv2.COLOR_RGB2HSV)
        pixels = top_half_hsv.reshape(-1, 3)
        
        # Find dominant colors using 2 clusters (player color vs background/grass)
        kmeans = KMeans(n_clusters=2, n_init=1).fit(pixels)
        labels = kmeans.labels_
        
        # Determine which cluster is the player vs the background corners
        clustered_img = labels.reshape(top_half.shape[0], top_half.shape[1])
        corner_clusters = [clustered_img[0,0], clustered_img[0,-1], clustered_img[-1,0], clustered_img[-1,-1]]
        bg_cluster = max(set(corner_clusters), key=corner_clusters.count)
        
        player_cluster = 1 - bg_cluster
        return kmeans.cluster_centers_[player_cluster]

    def assign_team_color(self, frame, first_frame_players):
        player_colors = []
        for player_id, track in first_frame_players.items():
            color = self.get_player_color(frame, track['bbox'])
            player_colors.append(color)
            
        # Cluster all player colors into 2 distinct teams
        self.kmeans = KMeans(n_clusters=2, init="k-means++", n_init="auto").fit(player_colors)
        
        self.team_colors[1] = self.kmeans.cluster_centers_[0]
        self.team_colors[2] = self.kmeans.cluster_centers_[1]

    def get_player_team(self, frame, bbox):
        color = self.get_player_color(frame, bbox)
        team_id = self.kmeans.predict(color.reshape(1, -1))[0]
        # returns 0 or 1 (mapped to Team 1 or Team 2)
        return team_id + 1 
```

---

## 5. Speed and Distance Estimation

**Why borrow:** Using the perspective-transformed coordinates (meters), we can calculate accurate physical metrics over a rolling window (e.g., 5 frames).

**Code Snippet (`speed_distance_estimator.py`):**

```python
import numpy as np

class SpeedAndDistanceEstimator:
    def __init__(self, frame_rate=24, frame_window=5):
        self.frame_rate = frame_rate
        self.frame_window = frame_window # Calculate speed every X frames to smooth noise
    
    def add_metrics_to_tracks(self, tracks):
        total_distance = {}

        for object_type, object_tracks in tracks.items():
            if object_type in ["ball", "referees"]:
                continue 
                
            num_frames = len(object_tracks)
            for frame_num in range(0, num_frames, self.frame_window):
                last_frame = min(frame_num + self.frame_window, num_frames - 1)

                for track_id in object_tracks[frame_num].keys():
                    if track_id not in object_tracks[last_frame]:
                        continue

                    # These MUST be the perspective-transformed coordinates (meters)
                    start_pos = object_tracks[frame_num][track_id].get('position_transformed')
                    end_pos = object_tracks[last_frame][track_id].get('position_transformed')

                    if start_pos is None or end_pos is None:
                        continue
                    
                    # Calculate Euclidean distance in meters
                    dist_covered = np.linalg.norm(np.array(end_pos) - np.array(start_pos))
                    
                    time_elapsed = (last_frame - frame_num) / self.frame_rate
                    speed_mps = dist_covered / time_elapsed
                    speed_kmh = speed_mps * 3.6

                    # Accumulate distance
                    if track_id not in total_distance:
                        total_distance[track_id] = 0
                    total_distance[track_id] += dist_covered

                    # Backfill the calculated data into the tracks dict for the window
                    for f in range(frame_num, last_frame):
                        if track_id in tracks[object_type][f]:
                            tracks[object_type][f][track_id]['speed_kmh'] = speed_kmh
                            tracks[object_type][f][track_id]['distance_m'] = total_distance[track_id]
```
