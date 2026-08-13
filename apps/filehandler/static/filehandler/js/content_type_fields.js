(function () {
    "use strict";

    function setVisible(selector, visible) {
        document.querySelectorAll(selector).forEach(function (element) {
            element.style.display = visible ? "" : "none";
        });
    }

    function updateContentFields() {
        var typeField = document.getElementById("id_file_type");
        if (!typeField) {
            return;
        }

        var contentType = typeField.value;
        setVisible(".article-fields", contentType === "article");
        setVisible(".file-fields", ["video", "document", "file"].indexOf(contentType) !== -1);
        setVisible(".activity-fields", contentType === "activity");
    }

    document.addEventListener("DOMContentLoaded", function () {
        var typeField = document.getElementById("id_file_type");
        if (!typeField) {
            return;
        }
        typeField.addEventListener("change", updateContentFields);
        updateContentFields();
    });
}());
