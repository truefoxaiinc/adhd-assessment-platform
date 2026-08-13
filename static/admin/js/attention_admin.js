(function () {
    "use strict";

    function enhanceAdmin() {
        document.documentElement.classList.add("minder-admin");

        document.querySelectorAll("#changelist-form .results").forEach(function (tableWrap) {
            tableWrap.setAttribute("role", "region");
            tableWrap.setAttribute("aria-label", "Scrollable data table");
            tableWrap.setAttribute("tabindex", "0");
        });

        document.querySelectorAll("input[type='search'], #searchbar").forEach(function (input) {
            input.setAttribute("inputmode", "search");
            input.setAttribute("autocomplete", "off");
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", enhanceAdmin);
    } else {
        enhanceAdmin();
    }
})();
