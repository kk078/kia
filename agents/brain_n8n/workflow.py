"""Workflow builder for creating n8n workflows programmatically."""

from typing import Any


class WorkflowBuilder:
    """Builder for creating n8n workflows."""

    def __init__(self, name: str) -> None:
        """Initialize workflow builder.

        Args:
            name: Workflow name
        """
        self.name = name
        self.nodes: list[dict[str, Any]] = []
        self.connections: dict[str, Any] = {}
        self.settings: dict[str, Any] = {}

    def add_node(
        self,
        node_type: str,
        name: str,
        parameters: dict[str, Any] | None = None,
        position: tuple[int, int] = (0, 0),
    ) -> "WorkflowBuilder":
        """Add a node to the workflow.

        Args:
            node_type: n8n node type (e.g., "n8n-nodes-base.httpRequest")
            name: Node name
            parameters: Node parameters
            position: Node position (x, y)

        Returns:
            Self for chaining
        """
        node = {
            "type": node_type,
            "typeVersion": 1,
            "name": name,
            "position": list(position),
            "parameters": parameters or {},
        }
        self.nodes.append(node)
        return self

    def add_webhook_trigger(
        self,
        name: str = "Webhook",
        path: str = "webhook",
        method: str = "POST",
    ) -> "WorkflowBuilder":
        """Add a webhook trigger node.

        Args:
            name: Node name
            path: Webhook path
            method: HTTP method

        Returns:
            Self for chaining
        """
        return self.add_node(
            node_type="n8n-nodes-base.webhook",
            name=name,
            parameters={
                "path": path,
                "httpMethod": method,
                "responseMode": "responseNode",
            },
            position=(0, 0),
        )

    def add_http_request(
        self,
        name: str,
        url: str,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        body: dict[str, Any] | None = None,
    ) -> "WorkflowBuilder":
        """Add an HTTP request node.

        Args:
            name: Node name
            url: Request URL
            method: HTTP method
            headers: Request headers
            body: Request body

        Returns:
            Self for chaining
        """
        params: dict[str, Any] = {
            "url": url,
            "method": method,
        }
        if headers:
            params["headerParameters"] = {
                "parameters": [{"name": k, "value": v} for k, v in headers.items()]
            }
        if body:
            params["bodyParameters"] = {"parameters": body}

        return self.add_node(
            node_type="n8n-nodes-base.httpRequest",
            name=name,
            parameters=params,
            position=(len(self.nodes) * 200, 0),
        )

    def add_code_node(
        self,
        name: str,
        code: str,
        language: str = "javaScript",
    ) -> "WorkflowBuilder":
        """Add a code execution node.

        Args:
            name: Node name
            code: Code to execute
            language: Code language (javaScript, python)

        Returns:
            Self for chaining
        """
        return self.add_node(
            node_type="n8n-nodes-base.code",
            name=name,
            parameters={
                "jsCode": code if language == "javaScript" else "",
                "pythonCode": code if language == "python" else "",
                "language": language,
            },
            position=(len(self.nodes) * 200, 0),
        )

    def connect(self, source: str, target: str) -> "WorkflowBuilder":
        """Connect two nodes.

        Args:
            source: Source node name
            target: Target node name

        Returns:
            Self for chaining
        """
        if source not in self.connections:
            self.connections[source] = {"main": [[]]}

        self.connections[source]["main"][0].append({"node": target, "type": "main", "index": 0})
        return self

    def set_settings(self, **kwargs: Any) -> "WorkflowBuilder":
        """Set workflow settings.

        Args:
            **kwargs: Settings key-value pairs

        Returns:
            Self for chaining
        """
        self.settings.update(kwargs)
        return self

    def build(self) -> dict[str, Any]:
        """Build the workflow definition.

        Returns:
            Workflow dict ready for n8n
        """
        return {
            "name": self.name,
            "nodes": self.nodes,
            "connections": self.connections,
            "settings": self.settings,
            "active": False,
        }

    @staticmethod
    def create_simple_webhook_workflow(
        name: str,
        webhook_path: str,
        target_url: str,
    ) -> dict[str, Any]:
        """Create a simple webhook → HTTP request workflow.

        Args:
            name: Workflow name
            webhook_path: Webhook path
            target_url: Target URL for HTTP request

        Returns:
            Workflow dict
        """
        builder = WorkflowBuilder(name)
        builder.add_webhook_trigger(path=webhook_path)
        builder.add_http_request(name="HTTP Request", url=target_url, method="POST")
        builder.connect("Webhook", "HTTP Request")
        return builder.build()
