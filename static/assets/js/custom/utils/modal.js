const Modal = {
    // Reusable Delete Modal
    showDeleteModal: function (heading, description, confirmText = "Delete", cancelText = "Cancel") {
        return Swal.fire({
            html: `
                <div class="flex flex-col gap-y-3">
                    <div class="w-[50px] h-[50px] bg-[#feebeb] rounded-[37px] m-auto flex items-center justify-center mb-1">
                        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="20" viewBox="0 0 24 20" fill="none">
                          <path d="M22.6875 14.4876L14.6625 1.5751C14.025 0.712597 13.05 0.225098 12 0.225098C10.9125 0.225098 9.93753 0.712597 9.33753 1.5751L1.31253 14.4876C0.562527 15.5001 0.450027 16.8126 1.01253 17.9376C1.57503 19.0626 2.70003 19.7751 3.97503 19.7751H20.025C21.3 19.7751 22.425 19.0626 22.9875 17.9376C23.55 16.8501 23.4375 15.5001 22.6875 14.4876ZM21.4875 17.1876C21.1875 17.7501 20.6625 18.0876 20.025 18.0876H3.97503C3.33753 18.0876 2.81253 17.7501 2.51253 17.1876C2.25003 16.6251 2.28753 15.9876 2.66253 15.5001L10.6875 2.5876C10.9875 2.1751 11.475 1.9126 12 1.9126C12.525 1.9126 13.0125 2.1376 13.3125 2.5876L21.3375 15.5001C21.7125 15.9876 21.75 16.6251 21.4875 17.1876Z" fill="#E10E0E"/>
                          <path d="M12.0002 7.2002C11.5502 7.2002 11.1377 7.5752 11.1377 8.0627V12.1502C11.1377 12.6002 11.5127 13.0127 12.0002 13.0127C12.4877 13.0127 12.8627 12.6377 12.8627 12.1502V8.0252C12.8627 7.5752 12.4502 7.2002 12.0002 7.2002Z" fill="#E10E0E"/>
                          <path d="M12.0002 14C11.5502 14 11.1377 14.375 11.1377 14.8625V15.05C11.1377 15.5 11.5127 15.9125 12.0002 15.9125C12.4877 15.9125 12.8627 15.5375 12.8627 15.05V14.825C12.8627 14.375 12.4502 14 12.0002 14Z" fill="#E10E0E"/>
                        </svg>
                    </div>
                    <p class="text-center text-zinc-950 text-xl font-semibold">${heading}</p>
                    <p class="text-center text-slate-500 text-sm font-normal leading-normal">${description}</p>
                </div>
            `,
            showCancelButton: true,
            buttonsStyling: false,
            confirmButtonText: confirmText,
            cancelButtonText: cancelText,
            allowOutsideClick: false,
            customClass: {
                container: 'delete-popup-container',
                popup: 'delete-popup',
                loader: 'hidden'
            },
        });
    },
};