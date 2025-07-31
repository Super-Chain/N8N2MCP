/*
 * -------------------------
 * Main Application Logic
 * -------------------------
 * This file contains the main application logic, tying together the API and UI
 * classes to create the full frontend experience. It initializes the app,
 * fetches data from the backend, and handles user interactions.
 */
class App {
    constructor() {
        this.api = new Api();
        this.ui = new UI();
        this.init();
    }

    /*
     * Initializes the application by fetching initial data and rendering the UI.
     */
    async init() {
        this.ui.showLoading();
        try {
            const workflows = await this.api.getUserUploadedWorkflows();
            const mcpServers = await this.api.getMcpServers();
            this.renderWorkflows(workflows, mcpServers);
        } catch (error) {
            console.error('Error initializing the app:', error);
            this.ui.render('<p>Error loading data. Please try again later.</p>');
        }
    }

    /*
     * Renders the main workflows page.
     * @param {Array} workflows - The list of user-uploaded workflows.
     * @param {Array} mcpServers - The list of MCP servers.
     */
    renderWorkflows(workflows, mcpServers) {
        const html = `
            <div class="container">
                <div class="header">
                    <h1 class="main-title">N8N <span class="highlight">2</span> MCP</h1>
                    <p class="subtitle">Import N8N workflow templates and deploy them as your MCP servers</p>
                </div>
                <div class="search-section">
                    <input type="text" id="workflow-url" class="search-bar" placeholder="Enter N8N workflow URL...">
                    <button id="import-workflow-btn" class="import-btn">Import Workflow</button>
                </div>
                <div class="workflows-grid">
                    ${workflows.map(workflow => this.renderWorkflowCard(workflow)).join('')}
                </div>
                <div class="mcp-servers-grid">
                    ${mcpServers.map(server => this.renderMcpServerCard(server)).join('')}
                </div>
            </div>
        `;
        this.ui.render(html);

        const importBtn = document.getElementById('import-workflow-btn');
        importBtn.addEventListener('click', () => {
            const url = document.getElementById('workflow-url').value;
            this.importWorkflow(url);
        });
    }

    /*
     * Renders a single workflow card.
     * @param {object} workflow - The workflow data.
     * @returns {string} - The HTML for the workflow card.
     */
    renderWorkflowCard(workflow) {
        return `
            <div class="card">
                <h3>${workflow.workflow_name}</h3>
                <p>${workflow.workflow_description}</p>
            </div>
        `;
    }

    /*
     * Renders a single MCP server card.
     * @param {object} server - The MCP server data.
     * @returns {string} - The HTML for the MCP server card.
     */
    renderMcpServerCard(server) {
        return `
            <div class="card">
                <h3>${server.workflow_name}</h3>
                <p>Status: ${server.status}</p>
            </div>
        `;
    }

    /*
     * Imports a workflow from the given URL.
     * @param {string} url - The URL of the workflow to import.
     */
    async importWorkflow(url) {
        if (!url) {
            this.ui.showModal('Please enter a workflow URL.');
            return;
        }

        this.ui.showLoading();
        try {
            const result = await this.api.importWorkflowFromUrl(url);
            if (result.success) {
                this.ui.showModal('Workflow imported successfully!');
                this.init();
            } else {
                this.ui.showModal(`Error: ${result.error}`);
            }
        } catch (error) {
            console.error('Error importing workflow:', error);
            this.ui.showModal('An error occurred while importing the workflow.');
        }
    }
}

// Initialize the application
new App();
