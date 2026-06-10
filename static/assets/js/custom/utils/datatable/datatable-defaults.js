// Set default options for datatable
$.extend($.fn.dataTable.defaults, {
    paging: true,
    pagingType: 'simple',
    pageLength: 5,
    lengthMenu: [5, 10, 25, 50],
    lengthChange: true,
    layout: {
        bottomStart: {
            features: [function (settings) {
                return `<span id="${settings.sTableId}SelectedCount">0 row(s) selected.</span>`
            }],
            className: 'flex items-center py-2 text-sm text-zinc-600'
        },
        bottomEnd: {
            features: ['pageLength', 'paging'],
            className: 'flex items-center justify-end gap-x-9 py-2'
        }
    },
    language: {
        lengthMenu: '<span class="text-zinc-950 text-sm">Rows per page _MENU_</span>',
        paginate: {
            previous: 'Previous',
            next: 'Next'
        },
    },
    order: [[1, 'asc']],
    searchDelay: 500,
    serverSide: true,
    responsive: true,
    processing: true,
    select: {
        style: 'multi',
        selector: 'td:first-child input[type="checkbox"]',
        className: 'row-selected',
    },
    initComplete: function (settings) {
        const tableId = settings.sTableId;
        const tableApi = this.api();

        // Add custom searchbar
        const searchInputHTML = `
                <div class="flex items-center bg-white border border-zinc-200 text-zinc-500 text-sm font-normal py-2 px-3 rounded-md focus-within:outline-none focus-within:ring-1 focus-within:ring-zinc-600">
                <img src="${api_config.search_icon}" alt="Search Icon" class="w-4 h-4 my-auto mr-2">
                <input type="text" placeholder="Type a command or search..." class="${tableId}-custom-search bg-transparent focus:outline-none text-sm text-zinc-500 placeholder-zinc-400 w-full">
                </div>
            `;
        $(`.${tableId}-search-container`).html(searchInputHTML);

        $(`.${tableId}-custom-search`).on('keyup', function () {
            tableApi.search(this.value.trim()).draw();
        });

        // Update selected count
        const updateSelectedCount = () => {
            const selectedCount = $(`#${tableId} tbody input[type="checkbox"]:checked`).length;

            $(`#${tableId}SelectedCount`).html(`${selectedCount} row(s) selected.`);
        };

        // Individual row selection
        $(`#${tableId} tbody`).on('change', 'input[type="checkbox"]', function () {
            if (!this.checked) {
                let el = $(`#${tableId} #selectAll`).get(0);
                if (el && el.checked) {
                    el.checked = false;
                }
            }
            updateSelectedCount();
        });

        // Select all rows
        $(`#${tableId} #selectAll`).on('click', function () {
            const rows = tableApi.rows().nodes();
            $('.rowCheckbox cursor-pointer', rows).prop('checked', this.checked);
            updateSelectedCount();
        });
    },
    drawCallback: function (settings) {
        const tableId = settings.sTableId;
        const tableApi = this.api();
        $(`#${tableId} td`).addClass('p-4 border-b');

        const searchKeyword = $(`.${tableId}-custom-search`).val()?.trim();
        const totalCount = tableApi.page.info().recordsTotal;
        const searchResultCount = tableApi.rows({ filter: 'applied' }).count();

        if(searchKeyword) {
            $(`#${tableId}-total`).html(`(${searchResultCount})`);
        } else {
            $(`#${tableId}-total`).html(`(${totalCount})`);
        }

        $(`#${tableId} #selectAll`).prop('checked', false);
        $(`#${tableId}SelectedCount`).html('0 row(s) selected.');
    }
});