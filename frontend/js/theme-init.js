/* Apply the cached theme before first paint to avoid a flash of the wrong theme. */
(function () {
    try {
        document.documentElement.dataset.theme = localStorage.getItem('theme') || 'light';
    } catch (_) {
        document.documentElement.dataset.theme = 'light';
    }
})();
