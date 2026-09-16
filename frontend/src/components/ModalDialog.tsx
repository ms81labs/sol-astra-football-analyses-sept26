import { useEffect, useRef, type ReactNode } from 'react';

export default function ModalDialog({ label, onClose, children }: {
  label: string;
  onClose: () => void;
  children: ReactNode;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = dialogRef.current!;
    const opener = document.activeElement as HTMLElement | null;
    dialog.showModal();
    (dialog.querySelector<HTMLElement>('[data-initial-focus], button, input, select, textarea') ?? dialog).focus();
    return () => {
      dialog.close();
      if (opener?.isConnected) opener.focus();
    };
  }, []);

  return (
    <dialog
      ref={dialogRef}
      aria-label={label}
      onCancel={(event) => { event.preventDefault(); onClose(); }}
      className="fixed inset-0 m-0 flex h-full max-h-none w-full max-w-none items-center justify-center border-0 bg-transparent p-4 text-slate-200 backdrop:bg-black/60"
    >
      {children}
    </dialog>
  );
}
