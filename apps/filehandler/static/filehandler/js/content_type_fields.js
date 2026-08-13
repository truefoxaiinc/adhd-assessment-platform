(function () {
    "use strict";

    function selectedTypeUrl(contentType) {
        var url = new URL(window.location.href);
        url.searchParams.set("type", contentType);
        return url.toString();
    }

    function updateContentFields() {
        var typeField = document.getElementById("id_file_type");
        if (!typeField) {
            return;
        }

        var renderedType = document.body.dataset.renderedContentType;
        if (!renderedType) {
            document.body.dataset.renderedContentType = typeField.value;
            return;
        }
        if (renderedType !== typeField.value) {
            var confirmed = window.confirm(
                "Change content type? The form will reload and unsaved values will be cleared."
            );
            if (confirmed) {
                window.location.assign(selectedTypeUrl(typeField.value));
            } else {
                typeField.value = renderedType;
            }
        }
    }

    document.addEventListener("DOMContentLoaded", function () {
        var typeField = document.getElementById("id_file_type");
        if (!typeField) {
            return;
        }
        document.body.dataset.renderedContentType = typeField.value;
        typeField.addEventListener("change", updateContentFields);
        updateContentFields();
    });
}());
