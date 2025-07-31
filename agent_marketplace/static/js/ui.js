/*
 * -------------------------
 * UI Management
 * -------------------------
 * This file provides a class for managing all UI-related functionality, such
 * as showing and hiding elements, creating dynamic content, and handling
 * animations. This helps to separate the UI logic from the application's
 * core logic.
 */
class UI {
    constructor() {
        this.app = document.getElementById('app');
    }

    /*
     * Renders the given HTML content in the main app container.
     * @param {string} html - The HTML content to render.
     */
    render(html) {
        this.app.innerHTML = html;
    }

    /*
     * Shows a loading spinner in the main app container.
     */
    showLoading() {
        this.app.innerHTML = '<div class="loading-spinner"></div>';
    }

    /*
     * Hides the loading spinner.
     */
    hideLoading() {
        // The loading spinner is removed when new content is rendered
    }

    /*
     * Shows a modal with the given content.
     * @param {string} content - The HTML content to display in the modal.
     */
    showModal(content) {
        const modal = document.createElement('div');
        modal.classList.add('modal');
        modal.innerHTML = `
            <div class="modal-content">
                <span class="close-btn">&times;</span>
                ${content}
            </div>
        `;
        document.body.appendChild(modal);

        const closeBtn = modal.querySelector('.close-btn');
        closeBtn.addEventListener('click', () => {
            this.hideModal();
        });

        modal.style.display = 'block';
    }

    /*
     * Hides the currently displayed modal.
     */
    hideModal() {
        const modal = document.querySelector('.modal');
        if (modal) {
            modal.remove();
        }
    }
}
