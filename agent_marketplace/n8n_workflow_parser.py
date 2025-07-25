import json
import re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

class CredentialType(Enum):
    API_KEY = "api_key"
    OAUTH2 = "oauth2"
    BASIC_AUTH = "basic_auth"
    BEARER_TOKEN = "bearer_token"
    DATABASE = "database"
    HTTP_HEADER = "http_header"
    WEBHOOK_URL = "webhook_url"
    CUSTOM = "custom"

class FieldType(Enum):
    TEXT = "text"
    PASSWORD = "password"
    EMAIL = "email"
    URL = "url"
    NUMBER = "number"
    SELECT = "select"
    TEXTAREA = "textarea"
    CHECKBOX = "checkbox"
    FILE = "file"

@dataclass
class CredentialField:
    name: str
    display_name: str
    field_type: FieldType
    required: bool = True
    description: str = ""
    placeholder: str = ""
    default_value: str = ""
    options: List[str] = field(default_factory=list)
    validation_pattern: str = ""
    help_text: str = ""

@dataclass
class ServiceCredential:
    service_name: str
    service_display_name: str
    credential_type: CredentialType
    fields: List[CredentialField]
    setup_instructions: str = ""
    documentation_url: str = ""
    icon_url: str = ""
    category: str = "general"

@dataclass
class WorkflowCredential:
    """Represents a credential requirement in an N8N workflow"""
    service_name: str
    credential_type: str
    required_fields: List[str]
    optional_fields: Optional[List[str]] = None
    description: str = ""
    node_names: Optional[List[str]] = None

@dataclass
class ParsedWorkflow:
    """Represents a parsed N8N workflow with extracted metadata"""
    workflow_name: str
    workflow_description: str
    total_nodes: int
    required_credentials: List[WorkflowCredential]
    node_types: List[str]
    connections: Dict[str, Any]
    raw_data: Dict[str, Any]
    complexity_score: float = 0.0  # Add complexity_score

class N8NWorkflowParser:
    """Parser for N8N workflow JSON files"""
    
    def __init__(self):
        self.parsed_workflows = {}
    
    def parse_workflow_file(self, file_path: str) -> ParsedWorkflow:
        """Parse N8N workflow from a JSON file"""
        with open(file_path, 'r', encoding='utf-8') as f:
            workflow_data = json.load(f)
            return self.parse_workflow_data(workflow_data)
    
    def parse_workflow_data(self, workflow_data: Dict[str, Any]) -> ParsedWorkflow:
        """Parse N8N workflow from JSON data"""
        # Extract basic workflow info
        workflow_name = workflow_data.get('template_name', 'Untitled Workflow')
        workflow_description = self._extract_description(workflow_data)
        
        # Extract nodes
        nodes = workflow_data.get('nodes', [])
        
        # Filter out non-functional nodes (documentation/visual elements)
        functional_nodes = [node for node in nodes if not self._is_non_functional_node(node)]
        total_nodes = len(functional_nodes)
        
        # Extract node types from all nodes (including non-functional for completeness)
        node_types = []
        for node in nodes:
            node_type = node.get('type', 'unknown')
            if node_type not in node_types:
                node_types.append(node_type)
        
        # Extract connections
        connections = workflow_data.get('connections', {})
        
        # Extract credential requirements from functional nodes only
        required_credentials = self._extract_credentials(functional_nodes)
        
        complexity_score = total_nodes * 1.5  # Simple calculation
        
        return ParsedWorkflow(
            workflow_name=workflow_name,
            workflow_description=workflow_description,
            total_nodes=total_nodes,
            required_credentials=required_credentials,
            node_types=node_types,
            connections=connections,
            raw_data=workflow_data,
            complexity_score=complexity_score
        )
    
    def _is_non_functional_node(self, node: Dict) -> bool:
        """Check if a node is non-functional (documentation/visual element)"""
        node_type = node.get('type', '').lower()
        
        # List of non-functional node types
        non_functional_types = {
            'n8n-nodes-base.stickynote',  # Sticky notes
            'n8n-nodes-base.note',        # Note nodes
            'n8n-nodes-base.annotation',  # Annotation nodes
            'n8n-nodes-base.comment',     # Comment nodes
        }
        
        return node_type in non_functional_types
    
    def _extract_description(self, workflow_data: Dict[str, Any]) -> str:
        """Extract workflow description from various sources"""
        # Try different places where description might be stored
        if 'meta' in workflow_data and 'description' in workflow_data['meta']:
            return workflow_data['meta']['description']
        
        if 'description' in workflow_data:
            return workflow_data['description']
        
        # Look for sticky notes that might contain descriptions
        nodes = workflow_data.get('nodes', [])
        for node in nodes:
            if node.get('type') == 'n8n-nodes-base.stickyNote':
                content = node.get('parameters', {}).get('content', '')
                if content and len(content) > 20:  # Likely a description
                    return content[:200] + '...' if len(content) > 200 else content
        
        return 'No description available'
    

    def _extract_credentials(self, nodes: List[Dict]) -> List[WorkflowCredential]:
        """Extract credential requirements from workflow nodes"""
        credentials = {}  # Use dict to avoid duplicates
        
        # Debug: Basic logging
        debug_enabled = False  # Set to True for detailed debugging
        if debug_enabled:
            print(f"🔍 DEBUG: Extracting credentials from {len(nodes)} functional nodes")
        
        for i, node in enumerate(nodes):
            node_type = node.get('type', '')
            node_name = node.get('name', 'Unknown Node')
            
            if debug_enabled:
                print(f"  Node {i+1}: {node_name} (type: {node_type})")
                
                # Log if node has credentials field
                node_credentials = node.get('credentials', {})
                if node_credentials:
                    # Check if credentials object is empty or has empty values
                    non_empty_creds = {k: v for k, v in node_credentials.items() if v}
                    if non_empty_creds:
                        print(f"    ✅ Has configured credentials: {list(non_empty_creds.keys())}")
                    else:
                        print(f"    ⚠️  Has empty credentials object: {list(node_credentials.keys())} (needs configuration)")
                else:
                    print(f"    ❌ No credentials field found")
                    # Check for other potential credential fields
                    for key in node.keys():
                        if 'cred' in key.lower() or 'auth' in key.lower() or 'token' in key.lower():
                            print(f"    🔍 Found potential credential field: {key} = {node[key]}")
            
            # Check if node requires credentials
            credential_info = self._get_credential_info(node_type, node)
            
            if credential_info:
                if debug_enabled:
                    print(f"    ✅ Credential info found: {credential_info['service_name']}")
                service_name = credential_info['service_name']
                
                if service_name not in credentials:
                    credentials[service_name] = WorkflowCredential(
                        service_name=service_name,
                        credential_type=credential_info['credential_type'],
                        required_fields=credential_info['required_fields'],
                        optional_fields=credential_info.get('optional_fields', []),
                        description=credential_info['description'],
                        node_names=[node_name]
                    )
                else:
                    # Add node name to existing credential
                    if credentials[service_name].node_names is None:
                        credentials[service_name].node_names = [node_name]
                    elif node_name not in credentials[service_name].node_names:
                        credentials[service_name].node_names.append(node_name)
            elif debug_enabled:
                print(f"    ❌ No credential info extracted")
        
        # Always log the final result
        print(f"Parsed workflow: {len(nodes)} functional nodes, {len(credentials)} services requiring credentials")
        for service_name, cred in credentials.items():
            print(f"  - {service_name}: {cred.credential_type} ({len(cred.required_fields)} fields)")
        
        return list(credentials.values())
    
    def _get_credential_info(self, node_type: str, node: Dict) -> Optional[Dict]:
        """Get credential information for a specific node type by parsing the JSON"""
        # Check for credentials in node configuration
        credentials = node.get('credentials', {})
        
        if credentials:
            # Process each credential type in the node
            for cred_type, cred_data in credentials.items():
                # Check if credential has actual data (id and name)
                if isinstance(cred_data, dict) and cred_data.get('id') and cred_data.get('name'):
                    # Extract service name from credential type or credential name
                    service_name = self._extract_service_name(cred_type, node_type, node)
                    
                    # For credentials with actual data, we can infer the service type better
                    # Use the credential name to get more context if available
                    cred_name = cred_data.get('name', '')
                    if cred_name:
                        # Try to extract more meaningful service name from the credential name
                        service_name = self._extract_service_from_cred_name(cred_name, cred_type, service_name)
                    
                    # Determine required fields based on credential type and node type
                    required_fields = self._determine_required_fields(cred_type, node_type, node)
                    
                    return {
                        'service_name': service_name,
                        'credential_type': cred_type,
                        'required_fields': required_fields,
                        'description': f'{service_name} credentials',
                        'credential_id': cred_data.get('id'),
                        'credential_name': cred_data.get('name')
                    }
        
        # Special case: if node has empty credentials object, it likely needs credentials
        # But skip this for agent nodes as they don't need direct credentials
        if 'credentials' in node and isinstance(node['credentials'], dict):
            empty_creds = node['credentials']
            if len(empty_creds) == 0 or all(not v for v in empty_creds.values()):
                # Skip agent nodes that don't actually need credentials
                if 'agent' in node_type.lower():
                    return None
                # print(f"    🎯 Node has empty credentials object - detecting service by node type")
                service_info = self._get_service_info_from_node_type(node_type, node)
                if service_info:
                    return service_info
        
        # Fallback: Check if this node type typically requires credentials based on common patterns
        # But only if the node actually has a credentials field (even if empty)
        if 'credentials' in node:
            service_info = self._get_service_info_from_node_type(node_type, node)
            if service_info:
                return service_info
        
        return None
    
    def _get_service_info_from_node_type(self, node_type: str, node: Dict) -> Optional[Dict]:
        """Determine if a node type typically requires credentials even if not explicitly defined"""
        # This method should only be used as a last resort when no credentials are found
        # Since we're focusing on dynamic extraction, we'll only handle special cases
        
        node_type_lower = node_type.lower()
        
        # Check for HTTP nodes that might need authentication
        if 'http' in node_type_lower and 'request' in node_type_lower:
            # Check if the node has authentication parameters that suggest it needs credentials
            parameters = node.get('parameters', {})
            authentication = parameters.get('authentication', '')
            
            if authentication or any(key in str(parameters).lower() for key in ['auth', 'token', 'key', 'bearer', 'basic']):
                return {
                    'service_name': 'HTTP API',
                    'credential_type': 'httpAuth',
                    'required_fields': self._determine_http_auth_fields(parameters),
                    'description': 'HTTP API credentials'
                }
        
        # For all other cases, return None since we want to rely on actual credentials in the workflow
        return None
    
    def _determine_http_auth_fields(self, parameters: Dict) -> List[str]:
        """Determine required fields for HTTP authentication based on parameters"""
        auth_type = parameters.get('authentication', '').lower()
        
        if 'basic' in auth_type:
            return ['username', 'password']
        elif 'bearer' in auth_type or 'token' in auth_type:
            return ['token']
        elif 'oauth' in auth_type:
            return ['client_id', 'client_secret']
        else:
            # Default to basic auth fields
            return ['username', 'password']
    
    def _extract_service_from_cred_name(self, cred_name: str, cred_type: str, fallback_service: str) -> str:
        """Extract service name from credential name with pattern matching"""
        # Common patterns in credential names
        # Example: "OpenAi_cred_system_1752747773" -> "OpenAI"
        # Example: "ClickUp account" -> "ClickUp"
        
        # Remove common suffixes and prefixes
        cleaned_name = cred_name
        for pattern in ['_cred_system_', '_cred_', '_account', ' account', ' Account', '_api', ' API', 
                       '_credential', ' credential', ' Credential', '_token', ' token', ' Token']:
            if pattern in cleaned_name:
                cleaned_name = cleaned_name.split(pattern)[0]
        
        # Remove trailing numbers and underscores
        cleaned_name = re.sub(r'[_\d]+$', '', cleaned_name).strip()
        
        # Handle underscores as word separators
        cleaned_name = cleaned_name.replace('_', ' ')
        
        # Handle camelCase and PascalCase
        # Insert spaces before capital letters
        cleaned_name = re.sub(r'([a-z])([A-Z])', r'\1 \2', cleaned_name)
        cleaned_name = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1 \2', cleaned_name)
        
        # If we got a meaningful name, use it
        if cleaned_name and len(cleaned_name) > 2:
            # Capitalize properly (handle special cases like "OpenAI")
            words = cleaned_name.split()
            formatted_words = []
            skip_next = False
            
            for i, word in enumerate(words):
                if skip_next:
                    skip_next = False
                    continue
                    
                word_lower = word.lower()
                if word_lower == 'openai' or (word_lower == 'open' and i + 1 < len(words) and words[i + 1].lower() == 'ai'):
                    formatted_words.append('OpenAI')
                    # Skip the next word if it's 'ai'
                    if i + 1 < len(words) and words[i + 1].lower() == 'ai':
                        skip_next = True
                elif word_lower == 'ai' and i > 0 and words[i - 1].lower() == 'open':
                    continue  # Skip 'ai' if preceded by 'open'
                elif word_lower == 'clickup' or (word_lower == 'click' and i + 1 < len(words) and words[i + 1].lower() == 'up'):
                    formatted_words.append('ClickUp')
                    # Skip the next word if it's 'up'
                    if i + 1 < len(words) and words[i + 1].lower() == 'up':
                        skip_next = True
                elif word_lower == 'up' and i > 0 and words[i - 1].lower() == 'click':
                    continue  # Skip 'up' if preceded by 'click'
                elif word_lower == 'api':
                    formatted_words.append('API')
                elif word_lower == 'oauth' or word_lower == 'oauth2':
                    formatted_words.append('OAuth')
                elif word_lower in ['my', 'your', 'the', 'a', 'an']:
                    # Skip common articles/possessives
                    continue
                elif word:  # Only add non-empty words
                    formatted_words.append(word.title())
            return ' '.join(formatted_words) if formatted_words else fallback_service
        
        # Otherwise, fall back to the provided service name
        return fallback_service

    def _extract_service_name(self, cred_type: str, node_type: str, node: Dict) -> str:
        """Extract service name from credential type and node information"""
        # First, try to get it from the credential name in the node
        credentials = node.get('credentials', {})
        cred_data = credentials.get(cred_type, {})
        cred_name = cred_data.get('name', '')
        
        if cred_name and cred_name != cred_type:
            # Use the helper method to extract service name from credential name
            return self._extract_service_from_cred_name(cred_name, cred_type, cred_type)
        
        # Fallback: Clean up the credential type to make it readable
        # Remove common suffixes and make it title case
        service_name = cred_type
        for suffix in ['Api', 'OAuth2', 'OAuth', 'Oauth2', 'api', 'oauth2', 'oauth']:
            if service_name.endswith(suffix):
                service_name = service_name[:-len(suffix)]
        
        # Handle camelCase and PascalCase
        # Insert spaces before capital letters
        import re
        service_name = re.sub(r'([a-z])([A-Z])', r'\1 \2', service_name)
        service_name = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1 \2', service_name)
        
        return service_name.strip().title()
    
    def _determine_required_fields(self, cred_type: str, node_type: str, node: Dict) -> List[str]:
        """Determine required fields based on credential type"""
        cred_lower = cred_type.lower()
        
        # Check for OAuth patterns
        if 'oauth2' in cred_lower or 'oauth' in cred_lower:
            return ['client_id', 'client_secret']
        
        # Check for basic auth patterns
        elif 'basicauth' in cred_lower or 'basic' in cred_lower:
            return ['username', 'password']
        
        # Check for token-based auth
        elif 'bearer' in cred_lower or 'token' in cred_lower or 'access' in cred_lower:
            return ['access_token']
        
        # Check for API key patterns
        elif 'api' in cred_lower or 'key' in cred_lower:
            return ['api_key']
        
        # Default fallback based on common patterns
        else:
            # If it ends with 'Api' it's likely an API key
            if cred_type.endswith('Api') or cred_type.endswith('api'):
                return ['api_key']
            # Otherwise default to access token
            else:
                return ['access_token']
    
    def generate_credential_form_config(self, parsed_workflow: ParsedWorkflow) -> Dict[str, Any]:
        """Generate form configuration for credential setup"""
        form_config = {
            'workflow_name': parsed_workflow.workflow_name,
            'description': f'Configure credentials for {parsed_workflow.workflow_name}',
            'credentials': []
        }
        
        for credential in parsed_workflow.required_credentials:
            cred_config = {
                'service_name': credential.service_name,
                'credential_type': credential.credential_type,
                'description': credential.description,
                'used_by_nodes': credential.node_names,
                'fields': []
            }
            
            # Add required fields
            for field in credential.required_fields:
                field_config = {
                    'name': field,
                    'display_name': self._format_field_label(field),
                    'type': self._get_field_type(field),
                    'required': True,
                    'placeholder': self._get_field_placeholder(field, credential.service_name)
                }
                cred_config['fields'].append(field_config)
            
            # Add optional fields
            if credential.optional_fields:
                for field in credential.optional_fields:
                    field_config = {
                        'name': field,
                        'display_name': self._format_field_label(field),
                        'type': self._get_field_type(field),
                        'required': False,
                        'placeholder': self._get_field_placeholder(field, credential.service_name)
                    }
                    cred_config['fields'].append(field_config)
            
            form_config['credentials'].append(cred_config)
        
        return form_config

    def _format_field_label(self, field_name: str) -> str:
        """Format field name into a readable label"""
        return field_name.replace('_', ' ').title()
    
    def _get_field_type(self, field_name: str) -> str:
        """Determine input field type based on field name"""
        if 'password' in field_name.lower() or 'secret' in field_name.lower():
            return 'password'
        elif 'email' in field_name.lower():
            return 'email'
        elif 'url' in field_name.lower() or 'endpoint' in field_name.lower():
            return 'url'
        elif 'token' in field_name.lower() or 'key' in field_name.lower():
            return 'password'
        else:
            return 'text'
    
    def _get_field_placeholder(self, field_name: str, service_name: str) -> str:
        """Generate placeholder text for form fields"""
        placeholders = {
            'api_key': f'Enter your {service_name} API key',
            'access_token': f'Enter your {service_name} access token',
            'client_id': f'Enter your {service_name} client ID',
            'client_secret': f'Enter your {service_name} client secret',
            'refresh_token': f'Enter your {service_name} refresh token',
            'username': 'Enter username',
            'password': 'Enter password',
            'email': 'Enter email address',
            'domain': 'Enter domain (optional)'
        }
        
        return placeholders.get(field_name, f'Enter {self._format_field_label(field_name).lower()}')