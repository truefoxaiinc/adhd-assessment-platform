function createSearchableSelect(parentId) {
    const parent = document.getElementById(parentId);
    const dropdownButton = parent.querySelector("button");
    const dropdownMenu = parent.querySelector("div");
    const searchInput = dropdownMenu.querySelector("input");
    const options = dropdownMenu.querySelectorAll("option");
    const hiddenInput = parent.querySelector("input[type=hidden]");
    let currentIndex = -1;

    function toggleDropdown() {     
        dropdownMenu.classList.toggle("hidden");
        if (!dropdownMenu.classList.contains("hidden")) searchInput.focus();
    };

    dropdownButton.onclick = (event) => {
        event.stopPropagation();
        if (!dropdownMenu.classList.contains("hidden")) {
            toggleDropdown();
        } else {
            closeAllDropdowns();
            toggleDropdown();
        }
    };

    //Open dropdown on ArrowDown key press
    dropdownButton.onkeydown = (event) => {
        if (event.key === "ArrowDown") {
            event.preventDefault();
            toggleDropdown();
        }
    };

    dropdownMenu.onclick = (event) => {
        event.stopPropagation();
    };

    options.forEach((option) => {
        option.onclick = (e) => {
            dropdownButton.classList.remove("text-gray-400");
            dropdownButton.classList.add("text-gray-700");
            dropdownButton.childNodes[0].nodeValue = e.target.innerText;
            hiddenInput.value = e.target.value;
            if (e.target.dataset.value) {
                hiddenInput.dataset.value = e.target.dataset.value;
            }
            hiddenInput.dispatchEvent(new Event("change"));
            hiddenInput.dispatchEvent(new Event("input"));
            toggleDropdown();
        };
        option.tabIndex = 0;
    });

    // Event listener to filter items based on input
    searchInput.oninput = (event) => {
        const searchTerm = searchInput.value.toLowerCase();
        options.forEach((option) => {
            const text = option.textContent.toLowerCase();
            option.style.display = text.includes(searchTerm) ? "block" : "none";
        });
        currentIndex = -1;
    };

    function handleClickOutside(event) {
        closeAllDropdowns();
    };
    
    function closeAllDropdowns() {        
        document.querySelectorAll(".relative.group").forEach((dropdown) => {
            dropdown.querySelector("div").classList.add("hidden");
        });
        // searchable multi select drop down
        document.querySelectorAll('#dropdownMenu').forEach((dropdown) => {
            dropdown.classList.add("hidden");
        });
    };

    document.onclick = (event) => {
        handleClickOutside(event);
        event.stopPropagation();
    };

    //Keyboard navigation
    dropdownMenu.onkeydown = (event) => {
        const visibleOptions = Array.from(options).filter(option => option.style.display !== "none");
        switch (event.key) { 
            case "ArrowDown":
                event.preventDefault();
                currentIndex = (currentIndex + 1) % visibleOptions.length;
                visibleOptions[currentIndex].focus();
                break;
            case "ArrowUp":
                event.preventDefault();
                currentIndex = (currentIndex - 1 + visibleOptions.length) % visibleOptions.length;
                visibleOptions[currentIndex].focus();
                break;
            case "Enter":
                event.preventDefault();
                visibleOptions[currentIndex].click();
                break;
            case "Escape":
                event.preventDefault();
                toggleDropdown();
                dropdownButton.focus(); // Return focus to the button
                break;
        }
    };

    // Prevent form submission on Enter key in search input 
    searchInput.onkeydown = (event) => {
        if (event.key === "Enter") event.preventDefault();
    };
};

function createSearchableMultiSelect(parentId) {
    const parent = document.getElementById(parentId);
    const dropdownButton = parent.querySelector("button");
    const dropdownMenu = parent.querySelector("#dropdownMenu");
    const searchInput = dropdownMenu.querySelector("input");
    const options = dropdownMenu.querySelectorAll("label");
    const checkedCountContainer = dropdownButton.querySelector("#checkedCountContainer");
    const checkedCountDisplay = checkedCountContainer.querySelector("span")
    const clearSelection = checkedCountContainer.querySelector("#clearSelection");
    const selectedItemsDisplay = dropdownButton.querySelector("p");
    const checkboxes = dropdownMenu.querySelectorAll("input[type=checkbox]");
    const hiddenInput = parent.querySelector("input[type=hidden]");
    let currentIndex = -1;

    function toggleDropdown() {
        dropdownMenu.classList.toggle("hidden");
        if (!dropdownMenu.classList.contains("hidden")) searchInput.focus();
    };

    dropdownButton.onclick = (e) => {
        e.stopPropagation();
        toggleDropdown();
    };

    //Open dropdown on ArrowDown key press
    dropdownButton.onkeydown = (event) => {
        if (event.key === "ArrowDown") {
            event.preventDefault();
            toggleDropdown();
        }
    };

    dropdownMenu.onclick = (e) => {
        e.stopPropagation();
    };

    // Filter items based on search
    searchInput.oninput = () => {
        const searchTerm = searchInput.value.toLowerCase();

        options.forEach((item) => {
            const text = item.textContent.toLowerCase();
            item.parentElement.style.display = text.includes(searchTerm) ? "block" : "none";
        });
    };

    // Function to count the number of checked checkboxes
    function updateCheckedCount() {
        const checkedCheckboxes = dropdownMenu.querySelectorAll('input[type="checkbox"]:checked');
        const checkedCategoryIds = [...checkedCheckboxes].map(checkbox => checkbox.value);
        const checkedCount = checkedCheckboxes.length;
        
        hiddenInput.value = checkedCategoryIds;
        hiddenInput.dispatchEvent(new Event("input"));
        checkedCountDisplay.textContent = checkedCount;

        if (checkedCount >= 2) {
            checkedCountContainer.classList.replace('hidden', 'inline-flex');
        } else {
            checkedCountContainer.classList.replace('inline-flex', 'hidden');
        }

        if (checkedCount > 0) {
            const selectedItems = [...checkedCheckboxes].map(checkbox => checkbox.parentElement.textContent.trim()).join(", ");
            selectedItemsDisplay.classList.replace("text-zinc-500", "text-zinc-950");
            selectedItemsDisplay.textContent = checkedCount === checkboxes.length ? "All Selected" : selectedItems;
        } else {
            selectedItemsDisplay.textContent = "Select";
            selectedItemsDisplay.classList.replace("text-zinc-950", "text-zinc-500");
        }
    }

    // Add event listeners to each checkbox to update the count on change
    checkboxes.forEach(checkbox => {
        checkbox.addEventListener("change", () => {
            updateCheckedCount();
        });
    });

    clearSelection.onclick = (e) => {
        e.stopPropagation();
        checkboxes.forEach(checkbox => {
            checkbox.checked = false;
        });

        hiddenInput.value = "";
        selectedItemsDisplay.textContent = "Select";
        selectedItemsDisplay.classList.replace("text-zinc-950", "text-zinc-500");
        checkedCountDisplay.textContent = "0";
        checkedCountContainer.classList.add("hidden");
    };

    //Keyboard navigation
    dropdownMenu.onkeydown = (event) => {        
        const visibleOptions = Array.from(options).filter(option => option.parentElement.style.display !== "none");
        switch (event.key) { 
            case "ArrowDown":
                event.preventDefault();
                currentIndex = (currentIndex + 1) % visibleOptions.length;
                visibleOptions[currentIndex].focus();
                break;
            case "ArrowUp":
                event.preventDefault();
                currentIndex = (currentIndex - 1 + visibleOptions.length) % visibleOptions.length;
                visibleOptions[currentIndex].focus();
                break;
            case "Enter":
                event.preventDefault();
                visibleOptions[currentIndex].click();
                break;
            case "Escape":             
                event.preventDefault();   
                toggleDropdown();
                dropdownButton.focus(); // Return focus to the button
                break;
        }
    };
}