// jsdom has no dialog implementation; modal focus containment belongs to the browser.
HTMLDialogElement.prototype.showModal = function () { this.open = true; };
HTMLDialogElement.prototype.close = function () { this.open = false; };
