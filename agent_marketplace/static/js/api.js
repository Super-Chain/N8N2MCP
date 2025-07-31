/*
 * -------------------------
 * API Abstraction Layer
 * -------------------------
 * This file provides a simple abstraction layer for making API calls to the
 * backend. It centralizes all API-related logic, making it easier to manage
 * and modify API endpoints in the future.
 */
class Api {
    constructor() {
        this.baseUrl = '/api';
    }

    /*
     * Performs a GET request to the specified endpoint.
     * @param {string} endpoint - The API endpoint to call.
     * @returns {Promise<any>} - The JSON response from the server.
     */
    async get(endpoint) {
        const response = await fetch(`${this.baseUrl}${endpoint}`);
        return response.json();
    }

    /*
     * Performs a POST request to the specified endpoint.
     * @param {string} endpoint - The API endpoint to call.
     * @param {object} data - The data to send in the request body.
     * @returns {Promise<any>} - The JSON response from the server.
     */
    async post(endpoint, data) {
        const response = await fetch(`${this.baseUrl}${endpoint}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data),
        });
        return response.json();
    }

    /*
     * Imports a workflow from a given URL.
     * @param {string} url - The URL of the workflow to import.
     * @returns {Promise<any>} - The JSON response from the server.
     */
    async importWorkflowFromUrl(url) {
        return this.post('/import-n8n-template-enhanced', { template_url: url });
    }

    /*
     * Deploys a workflow to the N8N instance.
     * @param {object} data - The workflow data to deploy.
     * @returns {Promise<any>} - The JSON response from the server.
     */
    async deployWorkflowToN8N(data) {
        return this.post('/deploy-workflow-to-n8n', data);
    }

    /*
     * Fetches the user's uploaded workflows.
     * @returns {Promise<any>} - The JSON response from the server.
     */
    async getUserUploadedWorkflows() {
        return this.get('/user/uploaded-workflows');
    }

    /*
     * Fetches the user's MCP servers.
     * @returns {Promise<any>} - The JSON response from the server.
     */
    async getMcpServers() {
        return this.get('/user/mcp-servers');
    }
}
