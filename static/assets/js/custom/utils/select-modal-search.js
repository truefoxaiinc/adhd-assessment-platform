function handleSelectModalSearch(modalId) {
    const searchInput = document.querySelector(`#${modalId} .modal-search`);
    const options = document.querySelectorAll(`#${modalId} .option-wrapper`);

    searchInput.addEventListener('input', function () {
        const searchValue = this.value.toLowerCase();

        options.forEach(option => {
            const text = option.textContent.toLowerCase(); 
            option.style.display = text.includes(searchValue) ? 'block' : 'none';
        });
    });
}