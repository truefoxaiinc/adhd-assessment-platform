'use strict';

function handleDatatableStatusFilter(dataTable, column, selector = '') {
    const statusForm = document.getElementById(`${selector}statusForm`);
    const display = document.querySelector(`#${selector}dropdownStatus span`);

    statusForm.onchange = function () {
        let value = document.querySelector('input[name="status"]:checked').value;
        display.classList.add('text-zinc-950');
        display.textContent = value;
        this.parentElement.classList.add('hidden');
        dataTable.column(column).search(value).draw();
    };

    statusForm.onreset = function () {
        display.classList.remove('text-zinc-950');
        display.textContent = 'Select';
        this.parentElement.classList.add('hidden');
        dataTable.column(column).search('').draw();
    };
};

function handleDatatableSort(dataTable, order_field, reset_field, selector = '') {
    const sortForm = document.getElementById(`${selector}sortForm`);
    const display = document.querySelector(`#${selector}dropdownSort span`);

    // Reset the sort form when the table is sorted by clicking on the header
    dataTable.on('order.dt', function (_e, ordArr) {
        if (typeof ordArr.aaSorting[0] != "number") {
            sortForm.setAttribute('data-reset-by-header', true);
            sortForm.reset();
        }
    });

    sortForm.onchange = function () {
        const selectedSort = sortForm.querySelector('input[name="sort"]:checked');
        display.textContent = selectedSort.value;
        this.parentElement.classList.add('hidden');
        dataTable.order([order_field, 'desc']).draw();
    };

    sortForm.onreset = function () {
        if (this.getAttribute('data-reset-by-header')) {
            this.removeAttribute('data-reset-by-header');
            return display.textContent = 'Name';
        }
        display.textContent = 'Name';
        this.parentElement.classList.add('hidden');
        dataTable.order([reset_field, 'asc']).draw();
    };
};

function handleDatatableStatusUpdate(dataTable, selector = '') {
    const kebabMenu = document.getElementById(`${selector}kebabMenu`);

    // Attach event listeners to each button
    kebabMenu.querySelectorAll('button[name="statusChange"]').forEach(function (button) {
        button.onclick = function () {
            let statusValue = this.id;
            let status = statusValue === 'setActive' ? 'active' : statusValue === 'setInactive' ? 'inactive' : 'deleteRow';
            this.parentElement.classList.add('hidden');
            // Collect selected checkboxes (get all checked items)
            let selectedIds = Array.from(document.querySelectorAll('.rowCheckbox:checked')).map(checkbox => checkbox.value);

            // Proceed only if there are selected checkboxes
            if (selectedIds.length > 0) {
                if (statusValue === 'deleteRows') {
                    Modal.showDeleteModal(
                        `Delete ${api_config.item}`,
                        `Are you sure you want to delete the selected row(s)? This process cannot be undone.`
                    ).then(function (result) {
                        if (!result.isConfirmed) return $('.swal2-container').addClass('!hidden');
                        if (result.value) executeAjaxRequest();
                    });
                } else if (statusValue === 'setInactive') {
                    Modal.showDeleteModal(
                        "Are you sure?",
                        `Do you want to mark the selected '${selector ? selector : api_config.item}' as inactive ?`,
                        "Yes"
                    ).then(function (result) {
                        if (!result.isConfirmed) return $('.swal2-container').addClass('!hidden');
                        if (result.value) executeAjaxRequest();
                    });
                } else {
                    executeAjaxRequest();
                }
            } else {
                Toast.showInfoToast('Please select at least one row.');
            }

            function executeAjaxRequest() {
                $.ajax({
                    method: "POST",
                    url: selector ? window[`${selector}_api_config`].status_change : api_config.status_change,
                    data: {
                        'csrfmiddlewaretoken': `${api_config.csrfmiddlewaretoken}`,
                        ids: selectedIds,
                        status: status === 'active',
                        statusvalue: statusValue
                    },
                    success: function (response) {
                        if (response.status_code == 200) {
                            if (statusValue === 'deleteRows') {
                                dataTable.draw();
                                Toast.showSuccessToast(
                                    'Deleted Successfully! '
                                )
                                updateSelectedCountryRows(status);
                            } else {
                                Toast.showSuccessToast(
                                    'Status changed successfully! '
                                )
                                updateSelectedCountryRows(status);
                            }
                        }
                        else {
                            Toast.showErrorToast(
                                `${response.message || "Please try again."}`
                            );
                        }
                    },
                    error: function (error) {
                        console.error('Error in AJAX request:', error);
                    }
                });
            }
        }
    });

    // Function to update the rows' status visually
    const updateSelectedCountryRows = (status) => {
        document.querySelectorAll('.rowCheckbox:checked').forEach(checkbox => {
            checkbox.checked = false;
            const row = checkbox.closest("tr");
            const statusCell = row.querySelector(`.${selector}status`);

            // Update status text and class
            statusCell.textContent = status;
            statusCell.classList.remove('text-activeGreen', 'bg-mintGreen', 'text-red', 'bg-pink');

            switch (status) {
                case "active":
                    statusCell.classList.add('text-activeGreen', 'bg-mintGreen');
                    break;
                case "inactive":
                    statusCell.classList.add('text-red', 'bg-pink');
                    break;
                case "deleteRow":
                    row.remove();
                    break;
                default:
                    break;
            }
        });
        // Uncheck the header checkbox
        document.querySelectorAll('#selectAll').forEach(checkbox => checkbox.checked = false);
    };
};