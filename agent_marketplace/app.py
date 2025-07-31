from flask import Flask, request, jsonify, render_template, send_from_directory  # type: ignore
from flask_cors import CORS  # type: ignore
import json
import os
import time
from datetime import datetime
import requests
from n8n_workflow_parser import N8NWorkflowParser
from database import db_manager
from dotenv import load_dotenv  # type: ignore

# Load environment variables from parent directory .env file
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

app = Flask(__name__)
CORS(app, supports_credentials=True)

# Initialize the workflow agent system
N8N_BASE_URL = os.getenv('N8N_BASE_URL', 'https://your-n8n-instance.com')
N8N_API_KEY = os.getenv('X_N8N_API_KEY', 'your-n8n-api-key')
N8N_BUILDER_URL = os.getenv('N8N_BUILDER_URL', 'https://u9r33hh89b.us-east-1.awsapprunner.com')
# Initialize the N8N parser
workflow_parser = N8NWorkflowParser()


@app.route('/')
def index():
    """Main workflows page - N8N integration interface"""
    return render_template('index.html')

@app.route('/api/health', methods=['GET'])
def health_check():
    """Simple health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'message': 'Agent Marketplace API is running',
        'endpoints': [
            '/api/parse-workflow',
            '/api/parse-workflow-json',
            '/api/parse-workflow-file',
            '/api/save-workflow-to-marketplace'
        ]
    })

# N8N Workflow Parser Endpoints
@app.route('/api/parse-workflow', methods=['POST'])
@app.route('/api/parse-workflow-json', methods=['POST'])  # Alias for backward compatibility
def parse_workflow():
    """
    Parse N8N workflow JSON and return credential form configuration
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Check if workflow JSON is provided
        workflow_json = data.get('workflow_json')
        if not workflow_json:
            return jsonify({'error': 'workflow_json is required'}), 400
        
        # Get manual workflow name from JSON data
        manual_workflow_name = data.get('manual_workflow_name', '').strip()
        
        # Parse the workflow
        parsed_workflow = workflow_parser.parse_workflow_data(workflow_json)
        
        # Override the workflow name with manual name if provided
        if manual_workflow_name:
            parsed_workflow.workflow_name = manual_workflow_name
            print(f"Using manual workflow name from JSON paste: {manual_workflow_name}")
        
        # Generate form configuration
        form_config = workflow_parser.generate_credential_form_config(parsed_workflow)
        
        is_user_upload = True  # Default to user upload for JSON paste
        template_id = None
        
        # Only classify as marketplace template if it has specific marketplace metadata
        if 'template_id' in workflow_json:
            template_id = workflow_json.get('template_id')
            is_user_upload = False
        elif workflow_json.get('meta', {}).get('templateId'):
            template_id = workflow_json.get('meta', {}).get('templateId')
            is_user_upload = False
        
        # Suggest appropriate endpoint based on workflow type
        suggested_endpoint = '/api/save-user-uploaded-workflow' if is_user_upload else '/api/save-workflow-to-marketplace'

        return jsonify({
            'success': True,
            'manual_workflow_name': manual_workflow_name,  # Include the manual name
            'workflow_info': {
                'name': parsed_workflow.workflow_name,
                'description': parsed_workflow.workflow_description,
                'total_nodes': parsed_workflow.total_nodes,
                'required_credentials': len(parsed_workflow.required_credentials)
            },
            'form_config': form_config,
            'is_user_upload': is_user_upload,
            'template_id': template_id,
            'suggested_endpoint': suggested_endpoint,
            'routing_info': {
                'user_upload_endpoint': '/api/save-user-uploaded-workflow',
            }
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/parse-workflow-file', methods=['POST'])
def parse_workflow_file():
    """
    Parse N8N workflow from uploaded file
    """
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not file.filename.endswith('.json'):
            return jsonify({'error': 'File must be a JSON file'}), 400
        
        # Get manual workflow name from form data
        manual_workflow_name = request.form.get('manual_workflow_name', '').strip()
        
        # Read and parse the file
        file_content = file.read().decode('utf-8')
        workflow_json = json.loads(file_content)
        
        # Parse the workflow
        parsed_workflow = workflow_parser.parse_workflow_data(workflow_json)
        
        # Override the workflow name with manual name if provided
        if manual_workflow_name:
            parsed_workflow.workflow_name = manual_workflow_name
            print(f"Using manual workflow name: {manual_workflow_name}")
        
        # Generate form configuration
        form_config = workflow_parser.generate_credential_form_config(parsed_workflow)
        
        is_user_upload = True  # Default to user upload for file uploads
        template_id = None
        
        # Only classify as marketplace template if it has specific marketplace metadata
        if 'template_id' in workflow_json:
            template_id = workflow_json.get('template_id')
            is_user_upload = False
        elif workflow_json.get('meta', {}).get('templateId'):
            template_id = workflow_json.get('meta', {}).get('templateId')
            is_user_upload = False
        # If uploaded via file, it's almost always a user upload regardless of having an 'id'
        
        # Suggest appropriate endpoint based on workflow type
        suggested_endpoint = '/api/save-user-uploaded-workflow' if is_user_upload else '/api/save-workflow-to-marketplace'
        
        return jsonify({
            'success': True,
            'filename': file.filename,
            'manual_workflow_name': manual_workflow_name,  # Include the manual name
            'workflow_info': {
                'name': parsed_workflow.workflow_name,
                'description': parsed_workflow.workflow_description,
                'total_nodes': parsed_workflow.total_nodes,
                'required_credentials': len(parsed_workflow.required_credentials)
            },
            'form_config': form_config,
            'workflow_json': workflow_json,  # Include the full workflow JSON
            'is_user_upload': is_user_upload,
            'template_id': template_id,
            'suggested_endpoint': suggested_endpoint,
            'routing_info': {
                'user_upload_endpoint': '/api/save-user-uploaded-workflow',
            }
        })
    
    except json.JSONDecodeError:
        return jsonify({'error': 'Invalid JSON file'}), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/validate-workflow', methods=['POST'])
def validate_workflow():
    """
    Validate N8N workflow JSON structure
    """
    try:
        data = request.get_json()
        workflow_json = data.get('workflow_json')
        
        if not workflow_json:
            return jsonify({'error': 'workflow_json is required'}), 400
        
        # Basic validation
        required_fields = ['nodes']
        missing_fields = [field for field in required_fields if field not in workflow_json]
        
        if missing_fields:
            return jsonify({
                'success': False,
                'error': f'Missing required fields: {", ".join(missing_fields)}'
            }), 400
        
        nodes = workflow_json.get('nodes', [])
        if not isinstance(nodes, list):
            return jsonify({
                'success': False,
                'error': 'nodes must be an array'
            }), 400
        
        if len(nodes) == 0:
            return jsonify({
                'success': False,
                'error': 'Workflow must contain at least one node'
            }), 400
        
        # Check node structure
        for i, node in enumerate(nodes):
            if not isinstance(node, dict):
                return jsonify({
                    'success': False,
                    'error': f'Node {i} must be an object'
                }), 400
            
            if 'type' not in node:
                return jsonify({
                    'success': False,
                    'error': f'Node {i} missing required field: type'
                }), 400
        
        return jsonify({
            'success': True,
            'message': 'Workflow is valid',
            'node_count': len(nodes)
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/import-n8n-template', methods=['POST'])
def import_n8n_template():
    """
    Import N8N workflow template from their public API
    """
    try:
        data = request.get_json()
        template_id = data.get('template_id')
        
        if not template_id:
            return jsonify({'error': 'template_id is required'}), 400
        
        template_url = f"https://api.n8n.io/api/workflows/templates/{template_id}"
        
        try:
            response = requests.get(template_url, timeout=30)
            response.raise_for_status()
            template_data = response.json()
        except requests.exceptions.RequestException as e:
            return jsonify({
                'success': False,
                'error': f'Failed to fetch template from N8N API: {str(e)}'
            }), 400
        
        # Check if template exists and is accessible
        if not template_data:
            return jsonify({
                'success': False,
                'error': 'Template not found or not accessible'
            }), 404
        
        # Extract workflow data
        workflow_data = template_data.get('workflow')
        if not workflow_data:
            return jsonify({
                'success': False,
                'error': 'No workflow data found in template'
            }), 400
        
        # Get template metadata
        template_name = template_data.get('name', f'N8N Template {template_id}')
        
        # Parse the workflow using existing parser
        parsed_workflow = workflow_parser.parse_workflow_data(workflow_data)
        
        # Generate form configuration
        form_config = workflow_parser.generate_credential_form_config(parsed_workflow)
        
        # Store the workflow locally (you might want to save this to a database)
        workflow_storage = {
            'template_id': template_id,
            'template_name': template_name,
            'original_url': f"https://n8n.io/workflows/{template_id}",
            'workflow_data': workflow_data,
            'imported_at': datetime.now().isoformat(),
            'parsed_data': {
                'name': parsed_workflow.workflow_name,
                'description': parsed_workflow.workflow_description,
                'total_nodes': parsed_workflow.total_nodes,
                'complexity_score': parsed_workflow.complexity_score,
                'required_credentials': len(parsed_workflow.required_credentials)
            }
        }
        
        return jsonify({
            'success': True,
            'template_id': template_id,
            'template_name': template_name,
            'template_url': f"https://n8n.io/workflows/{template_id}",
            'workflow_info': {
                'name': parsed_workflow.workflow_name or template_name,
                'description': parsed_workflow.workflow_description or 'Imported from N8N template library',
                'total_nodes': parsed_workflow.total_nodes,
                'required_credentials': len(parsed_workflow.required_credentials)
            },
            'form_config': form_config,
            'imported_at': workflow_storage['imported_at']
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# Enhanced workflow management with database integration
@app.route('/api/import-n8n-template-enhanced', methods=['POST'])
def import_n8n_template_enhanced():
    """
    Enhanced N8N template import with database storage and workflow creation
    """
    try:
        # No user authentication - use 'system' as default user
        user_id = 'system' # user is authenticated
        data = request.get_json()
        template_id = data.get('template_id')
        template_url = data.get('template_url', f"https://n8n.io/workflows/{template_id}")
        
        if not template_id:
            return jsonify({'error': 'template_id is required'}), 400
        
        # Fetch template from N8N API
        api_template_url = f"https://api.n8n.io/api/workflows/templates/{template_id}"
        
        try:
            response = requests.get(api_template_url, timeout=30)
            response.raise_for_status()
            template_data = response.json()
        except requests.exceptions.RequestException as e:
            return jsonify({
                'success': False,
                'error': f'Failed to fetch template from N8N API: {str(e)}'
            }), 400
        
        # Extract workflow data
        workflow_data = template_data.get('workflow')
        if not workflow_data:
            return jsonify({
                'success': False,
                'error': 'No workflow data found in template'
            }), 400
        
        # Get the template name from the top level (n8n API structure)
        template_name = template_data.get('name', f'N8N Template {template_id}')
        print(f"🔍 DEBUG: Template name extracted: '{template_name}'")
        
        # Parse the workflow (this will help with credentials and other metadata)
        parsed_workflow = workflow_parser.parse_workflow_data(workflow_data)
        print(f"🔍 DEBUG: Parsed workflow name (from workflow data): '{parsed_workflow.workflow_name}'")
        
        form_config = workflow_parser.generate_credential_form_config(parsed_workflow)
        
        # Create workflow in N8N instance
        n8n_workflow_id = None
        if db_manager.n8n_api_key:
            n8n_workflow_id = db_manager.create_n8n_workflow(workflow_data, template_name)
        
        # Save workflow to database - save to BOTH n8n_workflows and user_workflows
        credentials_required = [cred.service_name for cred in parsed_workflow.required_credentials]
        
        # Enhanced duplicate check across all sources
        existing_workflows = db_manager.get_user_uploaded_workflows(user_id, None)
        template_already_exists = False
        existing_workflow = None
        
        for existing in existing_workflows:
            # Check by template_id, workflow name, or workflow content similarity
            if (existing.get('template_id') == template_id or 
                existing.get('workflow_name') == template_name):
                template_already_exists = True
                existing_workflow = existing
                print(f"🔍 N8N template '{template_name}' (ID: {template_id}) already exists for user with source: {existing.get('source', 'unknown')}")
                break
        
        # save to user_workflows table (user's personal workflow management)
        if not template_already_exists:
            try:
                print(f"🔍 DEBUG: Saving workflow with name: '{template_name}'")
                db_manager.save_user_uploaded_workflow(
                    user_id=user_id,
                    workflow_name=template_name,
                    workflow_json=workflow_data,
                    workflow_description=f"N8N template imported from {template_url}",
                    credentials_required=credentials_required,
                    user_jwt=None,
                    n8n_workflow_id=n8n_workflow_id,
                    template_id=template_id,
                    source_override='n8n_template'
                )
                print(f"✅ Saved N8N template to user_workflows for user management")
            except Exception as user_save_error:
                print(f"⚠️ Warning: Failed to save N8N template to user_workflows: {user_save_error}")
        else:
            print(f"⏭️ Skipping save - N8N template already exists in user_workflows with source: {existing_workflow.get('source', 'unknown') if existing_workflow else 'unknown'}")
            # If the existing workflow doesn't have a template_id but this import does, update it
            if existing_workflow and not existing_workflow.get('template_id') and template_id:
                try:
                    db_manager.update_user_workflow_template_id(user_id, template_name, template_id)
                    print(f"📝 Updated existing workflow '{template_name}' with template_id: {template_id}")
                except Exception as update_error:
                    print(f"⚠️ Warning: Failed to update workflow with template_id: {update_error}")
        
        return jsonify({
            'success': True,
            'template_id': template_id,
            'template_name': template_name,
            'template_url': template_url,
            'workflow_info': {
                'name': parsed_workflow.workflow_name or template_name,
                'description': parsed_workflow.workflow_description or 'Imported from N8N template library',
                'total_nodes': parsed_workflow.total_nodes,
                'required_credentials': len(parsed_workflow.required_credentials)
            },
            'form_config': form_config,
            'n8n_workflow_id': n8n_workflow_id,
            'original_workflow': workflow_data,  # Include original clean workflow data
            'cached': False
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/deploy-workflow-to-n8n', methods=['POST'])
def deploy_workflow_to_n8n():
    """
    Deploy a workflow to the user's N8N workspace with their configured credentials
    """
    try:
        # No user authentication - use 'system' as default user
        user_id = 'system'
        data = request.get_json()
                
        # Check for direct deployment (workflow_json + user_credentials)
        workflow_json = data.get('workflow_json')
        frontend_credentials = data.get('user_credentials', {})
        workflow_name_override = data.get('workflow_name')
        workflow_description_override = data.get('workflow_description')  # Add description support
        
        # Check for template-based deployment
        template_id = data.get('template_id')
        workflow_id = data.get('workflow_id') or template_id
        
        workflow_data = None
        workflow_name = workflow_name_override 
        workflow_description = workflow_description_override  # Store description override
        user_credentials = {}
        workflow_source = None

        # Route 1: Direct deployment with workflow_json and credentials
        if workflow_json and frontend_credentials:
            workflow_data = workflow_json
            user_credentials = frontend_credentials
            workflow_source = 'direct'
            
            # Validate workflow data
            if not workflow_data.get('nodes'):
                return jsonify({'error': 'Invalid workflow JSON - missing nodes'}), 400
                
        # Route 2: Template-based deployment from database
        elif workflow_id:
            print(f"🚀 DEPLOYMENT: Using template-based deployment route for ID: {workflow_id}")
            
            # Try to get from user's uploaded workflows first
            user_workflows = db_manager.get_user_uploaded_workflows(user_id, None)
            user_workflow = next((w for w in user_workflows if w.get('template_id') == workflow_id or str(w.get('template_id')) == str(workflow_id)), None)
            
            if user_workflow:
                workflow_data = user_workflow.get('workflow_json')
                workflow_name = workflow_name_override or user_workflow.get('workflow_name', workflow_name)
                # Use override description or fallback to stored description
                workflow_description = workflow_description_override or user_workflow.get('workflow_description')
                workflow_source = 'user'
                
                # Parse JSON if it's stored as string
                if isinstance(workflow_data, str):
                    workflow_data = json.loads(workflow_data)
            
            if not workflow_data:
                return jsonify({
                    'error': f'Workflow not found with ID: {workflow_id}'
                }), 404
            
        else:
            return jsonify({
                'error': 'Either workflow_json + user_credentials OR template_id is required'
            }), 400

        
        # Get N8N configuration from environment variables
        n8n_instance_url = N8N_BASE_URL
        n8n_api_key = N8N_API_KEY or os.getenv('X_N8N_API_KEY')
        
        # Validate configuration
        if not n8n_instance_url or not n8n_api_key or n8n_instance_url == 'https://your-n8n-instance.com' or n8n_api_key == 'your-n8n-api-key':
            return jsonify({
                'error': 'N8N instance configuration missing. Please configure N8N_BASE_URL and N8N_API_KEY (or X_N8N_API_KEY) in your .env file.'
            }), 400
        
        # Create credentials in N8N instance first
        credential_mapping = create_credentials_in_n8n(n8n_instance_url, n8n_api_key, user_credentials, user_id)
        
        if not credential_mapping:
            print("⚠️ DEPLOYMENT: Failed to create credentials, proceeding without them")
            credential_mapping = {}
        
        # Prepare workflow data with N8N credential references
        prepared_workflow_data = prepare_workflow_with_n8n_credentials(workflow_data, credential_mapping, user_id)
        
        # Create workflow in N8N instance
        # Use user input name if provided, otherwise fallback to workflow JSON name
        if isinstance(workflow_name, str) and workflow_name.strip():
            # User provided a custom name - use it
            workflow_name = workflow_name.strip()
        else:
            # No user input - check workflow JSON for name
            workflow_name_from_json = None
            if isinstance(workflow_data, dict):
                workflow_name_from_json = workflow_data.get('name')
            if isinstance(workflow_name_from_json, str) and workflow_name_from_json.strip():
                workflow_name = workflow_name_from_json.strip()
            else:
                workflow_name = "Untitled Workflow"
        
        # Pass both name and description to N8N instance creation
        n8n_workflow_id = create_workflow_in_n8n_instance(
            n8n_instance_url, 
            n8n_api_key, 
            prepared_workflow_data, 
            workflow_name,
            workflow_description  # Pass custom description
        )
        
        if not n8n_workflow_id:
            return jsonify({
                'error': 'Failed to create workflow in N8N instance'
            }), 500
        
        # Update database with N8N workflow ID based on workflow source
        if workflow_source == 'direct':
            # Enhanced duplicate check - look for existing workflows by name, template_id, or content
            existing_workflows = db_manager.get_user_uploaded_workflows(user_id, None)
            existing_workflow = None
            
            # Check for duplicate by workflow name, template_id, or similar workflow data
            for existing in existing_workflows:
                if (existing.get('workflow_name') == workflow_name or 
                    (template_id and existing.get('template_id') == template_id)):
                    existing_workflow = existing
                    print(f"🔍 Found existing workflow: '{workflow_name}' (ID: {existing.get('template_id')}) with source: {existing.get('source', 'unknown')}")
                    break
            
            if existing_workflow:
                # Update existing workflow with N8N ID instead of creating duplicate
                print(f"📝 Updating existing workflow '{workflow_name}' with n8n_workflow_id: {n8n_workflow_id}")
                try:
                    db_manager.update_user_workflow_n8n_id(user_id, workflow_name, n8n_workflow_id)
                    print(f"  ▶ Successfully updated existing workflow with n8n ID.")
                    
                    # Also update source to 'deployed' to reflect it's now deployed
                    if existing_workflow.get('source') != 'deployed':
                        try:
                            db_manager.update_user_workflow_source(user_id, workflow_name, 'deployed')
                            print(f"  ▶ Updated workflow source to 'deployed'")
                        except Exception as source_update_error:
                            print(f"⚠️ Warning: Failed to update workflow source: {source_update_error}")
                            
                except Exception as update_error:
                    print(f"❌ Warning: Failed to update existing workflow: {update_error}")
            else:
                # For direct deployments, we must first save the workflow to get a record
                print(f"✍️ Saving new record for direct deployment of '{workflow_name}'")
                try:
                    # We need a stripped-down version of the workflow info to save
                    parsed_workflow = workflow_parser.parse_workflow_data(workflow_data)
                    credentials_required = [cred.service_name for cred in parsed_workflow.required_credentials]
                    
                    # Use custom description if provided, otherwise use parsed description
                    save_description = workflow_description or parsed_workflow.workflow_description

                    saved_workflow = db_manager.save_user_uploaded_workflow(
                        user_id=user_id,
                        workflow_name=workflow_name,
                        workflow_json=workflow_data,
                        workflow_description=save_description,  # Use custom or parsed description
                        credentials_required=credentials_required,
                        user_jwt=None,
                        n8n_workflow_id=n8n_workflow_id  # Save it with the n8n_id
                    )
                    if not saved_workflow:
                         raise Exception("Failed to save the new workflow record to the database.")
                    print(f"  ▶ Successfully saved direct deployment record for '{workflow_name}'.")

                except Exception as save_error:
                    print(f"❌ Critical error: Failed to save direct deployment workflow: {save_error}")
                    return jsonify({'error': f'Failed to save workflow record before deployment: {save_error}'}), 500

        elif template_id and workflow_source and workflow_source != 'direct':
            if workflow_source == 'user':
                # Update user_workflows table
                try:
                    db_manager.update_user_workflow_n8n_id(user_id, workflow_name, n8n_workflow_id)
                    print(f"Updated user workflow {workflow_name} with n8n_workflow_id: {n8n_workflow_id}")
                except Exception as update_error:
                    print(f"Warning: Failed to update user workflow n8n_id: {update_error}")
            elif workflow_source == 'marketplace':
                # Update n8n_workflows table  
                try:
                    db_manager.update_workflow_n8n_id(template_id, n8n_workflow_id, user_id)
                    print(f"Updated marketplace workflow {template_id} with n8n_workflow_id: {n8n_workflow_id}")
                except Exception as update_error:
                    print(f"Warning: Failed to update marketplace workflow n8n_id: {update_error}")
        
        # send POST request to n8n/build endpoint
        n8n_build_url = f"{N8N_BUILDER_URL}/n8n/build"
        
        n8n_build_payload = {
            "user_apikey": n8n_api_key,
            "workflow_id": n8n_workflow_id
        }

        try:
            print(f"🚀 Calling n8n/build endpoint at {n8n_build_url} with payload: {n8n_build_payload}")
            n8n_build_response = requests.post(n8n_build_url, json=n8n_build_payload, timeout=30)
            n8n_build_response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
            
            n8n_build_response_data = n8n_build_response.json()
            print(f"✅ n8n/build response: {n8n_build_response_data}")

            mcp_link = n8n_build_response_data.get('path')
            if not mcp_link:
                raise ValueError("Response from n8n/build is missing 'path' key.")
            mcp_link = f"{N8N_BUILDER_URL}{mcp_link}"
        except requests.exceptions.RequestException as e:
            print(f"❌ Error calling n8n/build endpoint: {e}")
            return jsonify({'error': f"Could not connect to the build service: {e}"}), 503
        except ValueError as e:
            print(f"❌ Invalid response from n8n/build: {e}")
            return jsonify({'error': f"Invalid response from build service: {e}"}), 500

        # update user_workflows table with mcp_link
        print(f"🔗 Updating workflow with n8n_workflow_id={n8n_workflow_id} for user={user_id} with MCP link: {mcp_link}")
        db_manager.update_user_workflow_mcp_link(user_id, n8n_workflow_id, mcp_link)

        return jsonify({
            'success': True,
            'message': 'Workflow deployed to N8N successfully!',
            'n8n_workflow_id': n8n_workflow_id,
            'workflow_name': workflow_name,
            'workflow_description': workflow_description,  # Include description in response
            'n8n_instance_url': n8n_instance_url,
            'workflow_url': f"{n8n_instance_url}/workflow/{n8n_workflow_id}",
            'credentials_used': list(user_credentials.keys()),
            'credentials_created': list(credential_mapping.keys()),
            'mcp_link': mcp_link
        })
        
    except Exception as e:
        print(f"Error deploying workflow to N8N: {e}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
    
@app.route('/api/save-user-uploaded-workflow', methods=['POST'])
def save_user_uploaded_workflow():
    """
    Save user-uploaded workflow directly to user_workflows table
    """
    try:
        # No user authentication - use 'system' as default user
        user_id = 'system'
        data = request.get_json()
        
        workflow_info = data.get('workflow_info', {})
        workflow_json = data.get('workflow_json', {})
        workflow_name = data.get('workflow_name') or workflow_info.get('name', 'Untitled Workflow')
        workflow_description = data.get('workflow_description') or workflow_info.get('description')
        
        if not workflow_json:
            return jsonify({'error': 'workflow_json is required'}), 400
        
        if not workflow_name:
            return jsonify({'error': 'workflow_name is required'}), 400
        
        # Extract credentials required from workflow using the parser
        credentials_required = []
        try:
            # Parse the workflow to extract actual credential requirements
            parsed_workflow = workflow_parser.parse_workflow_data(workflow_json)
            credentials_required = [cred.service_name for cred in parsed_workflow.required_credentials]
            print(f"🔍 Extracted {len(credentials_required)} credential requirements: {credentials_required}")
        except Exception as parser_error:
            print(f"Warning: Could not parse workflow for credentials: {parser_error}")
            # Fallback to provided credentials_required
            if 'required_credentials' in workflow_info:
                if isinstance(workflow_info['required_credentials'], list):
                    credentials_required = workflow_info['required_credentials']
                else:
                    credentials_required = [str(workflow_info['required_credentials'])]
        
        try:
            # Save the user-uploaded workflow directly to user_workflows table
            workflow_saved = db_manager.save_user_uploaded_workflow(
                user_id=user_id,
                workflow_name=workflow_name,
                workflow_json=workflow_json,
                workflow_description=workflow_description,
                credentials_required=credentials_required,
                user_jwt=None
            )
            
            if not workflow_saved:
                return jsonify({
                    'success': False,
                    'error': 'Failed to save user-uploaded workflow to database'
                }), 500
            
            # After successful database save, automatically create workflow in n8n backend
            n8n_workflow_id = None
            n8n_creation_success = False
            try:
                # Get N8N instance configuration from environment variables
                n8n_instance_url = N8N_BASE_URL
                n8n_api_key = N8N_API_KEY
                
                if n8n_instance_url and n8n_api_key and n8n_instance_url != 'https://your-n8n-instance.com' and n8n_api_key != 'your-n8n-api-key':
                    print(f"🚀 Creating workflow '{workflow_name}' in n8n backend...")
                    
                    # Create workflow in N8N instance
                    # Use the name from the workflow data if present, else fallback
                    workflow_name_from_json = None
                    if isinstance(workflow_json, dict):
                        workflow_name_from_json = workflow_json.get('name')
                    if isinstance(workflow_name_from_json, str) and workflow_name_from_json.strip():
                        workflow_name = workflow_name_from_json.strip()
                    elif not isinstance(workflow_name, str) or not workflow_name.strip():
                        workflow_name = "Untitled Workflow"
                    n8n_workflow_id = create_workflow_in_n8n_instance(
                        n8n_instance_url, 
                        n8n_api_key, 
                        workflow_json, 
                        workflow_name
                    )
                    
                    if n8n_workflow_id:
                        n8n_creation_success = True
                        print(f"✅ Successfully created n8n workflow with ID: {n8n_workflow_id}")
                        
                        # Update database with N8N workflow ID
                        try:
                            db_manager.update_user_workflow_n8n_id(user_id, workflow_name, n8n_workflow_id)
                            print(f"✅ Updated database with n8n workflow ID: {n8n_workflow_id}")
                        except Exception as update_error:
                            print(f"⚠️  Warning: Failed to update database with n8n ID: {update_error}")
                    else:
                        print(f"❌ Failed to create workflow in n8n backend")
                else:
                    print(f"⚠️  N8N configuration not found in environment - skipping n8n creation")
                    
            except Exception as n8n_error:
                print(f"❌ Error creating workflow in n8n backend: {n8n_error}")
                # Don't fail the entire request if n8n creation fails
            
            response_data = {
                'success': True,
                'message': 'User-uploaded workflow saved successfully',
                'workflow_name': workflow_name,
                'workflow_description': workflow_description,
                'saved_to_user_workflows': workflow_saved,
                'source': 'user_upload',
                'n8n_creation_attempted': True,
                'n8n_creation_success': n8n_creation_success
            }
            
            if n8n_workflow_id:
                response_data['n8n_workflow_id'] = n8n_workflow_id
                response_data['n8n_workflow_url'] = f"{n8n_instance_url}/workflow/{n8n_workflow_id}"
                
            return jsonify(response_data)
            
        except Exception as db_error:
            print(f"Database error: {db_error}")
            return jsonify({
                'success': False,
                'error': f'Failed to save user-uploaded workflow: {str(db_error)}'
            }), 500
    
    except Exception as e:
        print(f"Error in save_user_uploaded_workflow: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/user/uploaded-workflows', methods=['GET'])
def get_user_uploaded_workflows():
    """
    Get workflows uploaded directly by the current user
    """
    try:
        # No user authentication - use 'system' as default user
        user_id = 'system'
        workflows = db_manager.get_user_uploaded_workflows(user_id, None)
        return jsonify({
            'success': True,
            'workflows': workflows,
            'count': len(workflows)
        })
        
    except Exception as e:
        print(f"Error getting user-uploaded workflows: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# NOTE: Marketplace workflows endpoint removed as n8n_workflows table is no longer used
# All workflows are now stored in user_workflows table

@app.route('/api/user/uploaded-workflows/<template_id>', methods=['DELETE'])
def delete_user_uploaded_workflow(template_id):
    """
    Delete a user's uploaded workflow
    """
    try:
        # No user authentication - use 'system' as default user
        user_id = 'system'
        
        success = db_manager.delete_user_uploaded_workflow(user_id, template_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Workflow deleted successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Workflow not found or access denied'
            }), 404
            
    except Exception as e:
        print(f"Error deleting user uploaded workflow: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/user/mcp-servers', methods=['GET'])
def get_user_mcp_servers():
    """
    Get all MCP servers created by the current user from user_workflows table
    """
    try:
        # No user authentication - use 'system' as default user
        user_id = 'system'
        
        # Get workflows with MCP links from user_workflows table
        print(f"🔍 Fetching MCP servers for user_id: {user_id}")
        user_workflows = db_manager.get_user_uploaded_workflows(user_id, None)
        print(f"  ▶ Found {len(user_workflows)} total uploaded workflows for user.")
        
        # Filter workflows that have MCP links
        mcp_servers = []
        for workflow in user_workflows:
            mcp_link = workflow.get('mcp_link')
            n8n_id = workflow.get('n8n_workflow_id')
            
            if mcp_link and n8n_id:
                print(f"  ✅ Found MCP Server: {workflow.get('workflow_name')} (ID: {n8n_id}) with link: {mcp_link}")
                mcp_server = {
                    'workflow_name': workflow.get('workflow_name'),
                    'n8n_workflow_id': n8n_id,
                    'mcp_server_path': mcp_link,
                    'mcp_link': mcp_link,  # For backward compatibility
                    'template_id': workflow.get('template_id'),
                    'workflow_description': workflow.get('workflow_description'),
                    'created_at': workflow.get('created_at'),
                    'updated_at': workflow.get('updated_at'),
                    'mcp_build_success': True,  # Assume success if link exists
                    'source': workflow.get('source', 'unknown')
                }
                mcp_servers.append(mcp_server)
            else:
                print(f"  ⚠️ Workflow '{workflow.get('workflow_name')}' is missing mcp_link or n8n_workflow_id. Skipping.")
        
        # FALLBACK: Also get MCP servers from workflow_deployments for backward compatibility
        try:
            deployment_mcp_servers = db_manager.get_user_mcp_servers(user_id)
            for deployment_server in deployment_mcp_servers:
                # Only add if not already present from user_workflows
                n8n_id = deployment_server.get('n8n_workflow_id')
                if not any(server.get('n8n_workflow_id') == n8n_id for server in mcp_servers):
                    mcp_servers.append(deployment_server)
        except Exception as fallback_error:
            print(f"⚠️ Warning: Failed to get MCP servers from workflow_deployments (table may not exist): {fallback_error}")
        
        return jsonify({
            'success': True,
            'mcp_servers': mcp_servers,
            'count': len(mcp_servers)
        })
        
    except Exception as e:
        print(f"Error getting user MCP servers: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def prepare_workflow_with_n8n_credentials(workflow_json, credential_mapping, user_id):
    """
    Prepare workflow data by injecting N8N credential references into the appropriate nodes
    credential_mapping format: {service_name: {'id': 'cred_id', 'name': 'cred_name', 'type': 'cred_type'}}
    """
    try:
        workflow_data = workflow_json.copy()
        
        print(f"🔧 Preparing workflow with {len(credential_mapping)} credential mappings")
        
        if 'nodes' in workflow_data:
            for node in workflow_data['nodes']:
                node_type = node.get('type', '')
                node_name = node.get('name', 'Unknown Node')
                
                # Extract the actual service type from N8N node type
                # e.g., 'n8n-nodes-base.OpenAi' -> 'OpenAi'
                service_type = node_type.split('.')[-1] if '.' in node_type else node_type
                
                print(f"🔧 Processing node: {node_name} (type: {node_type}, service: {service_type})")
                
                # Find matching credential by service name
                matched_credential = None
                for service_name, cred_info in credential_mapping.items():
                    # Try exact match first
                    if service_name == service_type or service_name.lower() == service_type.lower():
                        matched_credential = cred_info
                        print(f"🔧 Exact match found: {service_name} -> {cred_info['id']}")
                        break
                    # Try partial matches
                    elif service_type.lower() in service_name.lower() or service_name.lower() in service_type.lower():
                        matched_credential = cred_info
                        print(f"🔧 Partial match found: {service_name} -> {cred_info['id']}")
                        break
                
                if matched_credential:
                    # Set credential reference in node
                    if 'credentials' not in node:
                        node['credentials'] = {}
                    
                    # Use the credential type from the mapping
                    credential_type = matched_credential['type']
                    
                    node['credentials'][credential_type] = {
                        'id': matched_credential['id'],
                        'name': matched_credential['name']
                    }
                    
                    print(f"✅ Applied credential {matched_credential['id']} to node {node_name}")
                else:
                    print(f"⚠️ No credential found for node: {node_name} (service: {service_type})")
                    
        print(f"🔧 Workflow preparation complete")
        return workflow_data
        
    except Exception as e:
        print(f"❌ Error preparing workflow with N8N credentials: {e}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        return workflow_json

def create_credentials_in_n8n(n8n_url, api_key, user_credentials, user_id):
    """
    Create individual credentials in the user's N8N instance for each service
    Returns a mapping of service names to N8N credential IDs
    """
    try:
        n8n_url = n8n_url.rstrip('/')
        
        credential_mapping = {}
        
        # Map service names to N8N credential types
        service_to_credential_type = {
            'OpenAI': 'openAiApi',
            'openai': 'openAiApi',
            'openAi': 'openAiApi',  # Handle case variations
            'LangChain Service': 'httpBasicAuth',  # Generic API key credential
            'langchain': 'httpBasicAuth',
            'Telegram': 'telegramApi',
            'telegram': 'telegramApi',
            'Slack': 'slackApi',
            'slack': 'slackApi',
            'Gmail': 'gmailOAuth2',
            'gmail': 'gmailOAuth2',
            'Google': 'googleOAuth2Api',
            'google': 'googleOAuth2Api',
            'GoogleSheets': 'googleSheetsOAuth2Api',
            'googleSheets': 'googleSheetsOAuth2Api',
            'Google Sheets': 'googleSheetsOAuth2Api',
            'GoogleDrive': 'googleDriveOAuth2Api',
            'googleDrive': 'googleDriveOAuth2Api',
            'Google Drive': 'googleDriveOAuth2Api',
            'Jira': 'jiraSoftwareCloudApi',
            'jira': 'jiraSoftwareCloudApi',
            'Notion': 'notionApi',
            'notion': 'notionApi',
            'Airtable': 'airtableTokenApi',
            'airtable': 'airtableTokenApi',
            'HTTP Request': 'httpBasicAuth',
            'httpRequest': 'httpBasicAuth'
        }
        
        headers = {
            'X-N8N-API-KEY': api_key,
            'Content-Type': 'application/json'
        }
        
        # Create credentials for each service
        for service_name, credentials in user_credentials.items():
            try:
                print(f"🔐 Creating N8N credential for {service_name}...")
                
                # Determine credential type
                credential_type = service_to_credential_type.get(service_name) or service_to_credential_type.get(service_name.lower())
                
                if not credential_type:
                    # Default to generic API key credential
                    credential_type = 'httpBasicAuth'
                    print(f"⚠️ Unknown service {service_name}, using default credential type: {credential_type}")
                
                # Prepare credential data based on the service
                credential_data = {}
                
                if credential_type == 'openAiApi':
                    # OpenAI API Key
                    credential_data = {
                        'apiKey': credentials.get('api_key') or credentials.get('apiKey', '')
                    }
                elif credential_type == 'telegramApi':
                    # Telegram Bot Token
                    credential_data = {
                        'accessToken': credentials.get('access_token') or credentials.get('bot_token') or credentials.get('token', '')
                    }
                elif credential_type in ['googleOAuth2Api', 'googleSheetsOAuth2Api', 'googleDriveOAuth2Api']:
                    # Google OAuth2 Services
                    credential_data = {
                        'clientId': credentials.get('client_id') or credentials.get('clientId', ''),
                        'clientSecret': credentials.get('client_secret') or credentials.get('clientSecret', ''),
                        'refreshToken': credentials.get('refresh_token') or credentials.get('refreshToken', ''),
                        'accessToken': credentials.get('access_token') or credentials.get('accessToken', '')
                    }
                elif credential_type == 'httpBasicAuth':
                    # Generic API Key (used for LangChain Service, HTTP Request, etc.)
                    credential_data = {
                        'user': credentials.get('user') or credentials.get('username') or 'api',
                        'password': credentials.get('api_key') or credentials.get('password') or credentials.get('key') or credentials.get('token', '')
                    }
                else:
                    # Default: try to map common field names
                    if 'api_key' in credentials:
                        credential_data = {'apiKey': credentials['api_key']}
                    elif 'access_token' in credentials:
                        credential_data = {'accessToken': credentials['access_token']}
                    elif 'token' in credentials:
                        credential_data = {'token': credentials['token']}
                    elif 'client_id' in credentials and 'client_secret' in credentials:
                        # OAuth2 pattern
                        credential_data = {
                            'clientId': credentials['client_id'],
                            'clientSecret': credentials['client_secret']
                        }
                        if 'refresh_token' in credentials:
                            credential_data['refreshToken'] = credentials['refresh_token']
                    else:
                        # Use the first available credential field
                        first_key = list(credentials.keys())[0] if credentials else 'apiKey'
                        credential_data = {first_key: list(credentials.values())[0] if credentials else ''}
                
                # Create credential payload
                credential_payload = {
                    'name': f"{service_name}_cred_{user_id}_{int(time.time())}",
                    'type': credential_type,
                    'data': credential_data
                }
                
                print(f"🔐 Creating {service_name} credential with type: {credential_type}")
                
                # API endpoint for creating credentials
                create_url = f"{n8n_url}/api/v1/credentials"
                
                response = requests.post(
                    create_url,
                    json=credential_payload,
                    headers=headers,
                    timeout=30
                )
                
                if response.status_code in [200, 201]:
                    credential_response = response.json()
                    credential_id = credential_response.get('id')
                    credential_name = credential_response.get('name')
                    
                    print(f"✅ Successfully created {service_name} credential: {credential_id}")
                    
                    # Store mapping for workflow preparation
                    credential_mapping[service_name] = {
                        'id': credential_id,
                        'name': credential_name,
                        'type': credential_type
                    }
                    
                else:
                    print(f"❌ Failed to create {service_name} credential. Status: {response.status_code}")
                    print(f"Response: {response.text}")
                    
            except Exception as service_error:
                print(f"❌ Error creating credential for {service_name}: {service_error}")
                continue
        
        print(f"🔐 Credential creation complete. Created {len(credential_mapping)} credentials.")
        return credential_mapping
        
    except Exception as e:
        print(f"❌ Error in create_credentials_in_n8n: {e}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        return None

def create_workflow_in_n8n_instance(n8n_url, api_key, workflow_data, workflow_name, workflow_description=None):
    """
    Create a workflow in the user's N8N instance
    """
    try:
        # Clean up the N8N URL
        n8n_url = n8n_url.rstrip('/')
        
        # Use custom description if provided, otherwise use description from workflow data
        final_description = workflow_description or workflow_data.get('description', '')
        
        # Prepare workflow payload using the correct N8N structure
        workflow_payload = {
            'name': workflow_name,
            'nodes': workflow_data.get('nodes', []),
            'connections': workflow_data.get('connections', {}),
            'settings': workflow_data.get('settings', {}),  # Use original settings or empty object
            'staticData': workflow_data.get('staticData', {}),
            'description': final_description  # Use custom or original description
        }
        
        # API endpoint for creating workflows
        create_url = f"{n8n_url}/api/v1/workflows"
        
        headers = {
            'X-N8N-API-KEY': api_key,
            'Content-Type': 'application/json'
        }
        
        print(f"🚀 Creating workflow in N8N with payload keys: {list(workflow_payload.keys())}")
        print(f"🚀 Workflow description: {final_description}")
        
        response = requests.post(
            create_url,
            json=workflow_payload,
            headers=headers,
            timeout=30
        )
        
        if response.status_code in [200, 201]:  # Accept both 200 and 201 as success
            workflow_response = response.json()
            n8n_workflow_id = workflow_response.get('id')
            
            if n8n_workflow_id:
                print(f"✅ Successfully created workflow with ID: {n8n_workflow_id}")
                return n8n_workflow_id
            else:
                print(f"⚠️ N8N API returned 200 but no workflow ID found")
                print(f"Response keys: {list(workflow_response.keys()) if isinstance(workflow_response, dict) else 'Not a dict'}")
                print(f"Full response (first 200 chars): {str(workflow_response)[:200]}...")
                return None
        else:
            print(f"❌ Failed to create workflow. Status: {response.status_code}")
            print(f"Response: {response.text}")
            
            # Try a minimal payload if the full one fails
            if response.status_code == 400:
                print("🔄 Trying minimal payload...")
                minimal_payload = {
                    'name': workflow_name,
                    'nodes': workflow_data.get('nodes', []),
                    'connections': workflow_data.get('connections', {}),
                    'settings': {}  # Include empty settings as it's required
                }
                
                response = requests.post(
                    create_url,
                    json=minimal_payload,
                    headers=headers,
                    timeout=30
                )
                
                if response.status_code in [200, 201]:
                    workflow_response = response.json()
                    n8n_workflow_id = workflow_response.get('id')
                    print(f"✅ Successfully created workflow with minimal payload. ID: {n8n_workflow_id}")
                    return n8n_workflow_id
                else:
                    print(f"❌ Minimal payload also failed. Status: {response.status_code}")
                    print(f"Response: {response.text}")
            
            return None
            
    except Exception as e:
        print(f"❌ Error creating workflow in N8N instance: {e}")
        return None

def clean_workflow_for_n8n_api(workflow_data):
    """
    Clean workflow data by removing read-only fields that cause N8N API errors
    """
    try:
        cleaned_data = workflow_data.copy()
        
        # Remove read-only fields that N8N manages internally
        read_only_fields = [
            'id', 'tags', 'createdAt', 'updatedAt', 'versionId', 
            'active', 'pinData', 'hash', 'meta'
        ]
        
        for field in read_only_fields:
            if field in cleaned_data:
                print(f"🧹 Removing read-only field: {field}")
                del cleaned_data[field]
        
        # Clean nodes - remove read-only node fields
        if 'nodes' in cleaned_data:
            for node in cleaned_data['nodes']:
                node_read_only_fields = ['id', 'webhookId']
                for field in node_read_only_fields:
                    if field in node:
                        del node[field]
        
        print(f"🧹 Cleaned workflow data. Remaining fields: {list(cleaned_data.keys())}")
        return cleaned_data
        
    except Exception as e:
        print(f"❌ Error cleaning workflow data: {e}")
        return workflow_data

if __name__ == '__main__':
    # Initialize database on startup
    try:
        db_manager.init_database()
        print("Database initialized successfully")
    except Exception as e:
        print(f"Warning: Database initialization failed: {e}")
        print("Application will run but database features may not work")
    
    # Get host and port from environment
    host = os.getenv('HOST', os.getenv('FLASK_HOST', '0.0.0.0'))
    port = int(os.getenv('PORT', os.getenv('FLASK_PORT', 5000)))
    
    print(f"Starting Flask app on http://{host}:{port}")
    app.run(debug=False, host=host, port=port) 