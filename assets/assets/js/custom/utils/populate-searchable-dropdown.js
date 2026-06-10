function populateSearchableDropdowns(selector, options) {
    const dropdown = document.querySelector(`#${selector} #options`);
    const dropdownButton = document.querySelector(`#${selector} button`);
    const hiddenInput = document.querySelector(`#${selector} input[type=hidden]`);

    // Reset selection
    dropdownButton.classList.remove("text-gray-700");
    dropdownButton.classList.add("text-gray-400");
    dropdownButton.childNodes[0].nodeValue = `Select ${selector.split('-')[0]}`;
    hiddenInput.value = "";
    hiddenInput.dispatchEvent(new Event("change"));

    // Clear current options
    dropdown.innerHTML = '';

    options.forEach(option => {
      const optionElement = document.createElement('option');
      optionElement.value = option.id;
      optionElement.textContent = option.name;
      optionElement.className = 'block px-4 py-2 text-gray-700 hover:bg-gray-100 focus:bg-gray-100 outline-none cursor-pointer rounded-md';
      dropdown.appendChild(optionElement);
    });
    createSearchableSelect(selector);
  }