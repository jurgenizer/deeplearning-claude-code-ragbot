import anthropic
from typing import List, Optional, Dict, Any

class AIGenerator:
    """Handles interactions with Anthropic's Claude API for generating responses"""

    MAX_TOOL_ROUNDS = 2

    SYSTEM_PROMPT = """ You are an AI assistant specialized in course materials and educational content with access to a comprehensive search tool for course information.

Search Tool Usage:
- Use the search tool **only** for questions about specific course content or detailed educational materials
- You may perform up to 2 sequential searches if a follow-up search is needed to answer the question fully (e.g., look up a course outline to find a lesson title, then search for that topic in another course)
- Synthesize all search results into a single accurate, fact-based response
- If search yields no results, state this clearly without offering alternatives

Outline Tool Usage:
- Use the `get_course_outline` tool for any query asking about a course outline, lesson list, course structure, or what lessons a course contains
- When the tool returns an outline, present **all** of the following in your response:
  - Course title
  - Course link
  - Every lesson with its lesson number and lesson title
- Do not omit or summarize the lesson list

Response Protocol:
- **General knowledge questions**: Answer using existing knowledge without searching
- **Course-specific questions**: Search first, then answer
- **Outline questions**: Use `get_course_outline`, then present the full structured result
- **No meta-commentary**:
 - Provide direct answers only — no reasoning process, search explanations, or question-type analysis
 - Do not mention "based on the search results"


All responses must be:
1. **Brief, Concise and focused** - Get to the point quickly
2. **Educational** - Maintain instructional value
3. **Clear** - Use accessible language
4. **Example-supported** - Include relevant examples when they aid understanding
Provide only the direct answer to what was asked.
"""

    def __init__(self, api_key: str, model: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

        self.base_params = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 800
        }

    def generate_response(self, query: str,
                          conversation_history: Optional[str] = None,
                          tools: Optional[List] = None,
                          tool_manager=None) -> str:
        system_content = (
            f"{self.SYSTEM_PROMPT}\n\nPrevious conversation:\n{conversation_history}"
            if conversation_history
            else self.SYSTEM_PROMPT
        )

        messages = [{"role": "user", "content": query}]

        api_params = {
            **self.base_params,
            "messages": messages,
            "system": system_content
        }

        if tools:
            api_params["tools"] = tools
            api_params["tool_choice"] = {"type": "auto"}

        response = self.client.messages.create(**api_params)

        tool_rounds = 0

        while (
            response.stop_reason == "tool_use"
            and tool_manager is not None
            and tool_rounds < self.MAX_TOOL_ROUNDS
        ):
            messages.append({"role": "assistant", "content": response.content})
            tool_results = self._execute_tool_calls(response, tool_manager)
            messages.append({"role": "user", "content": tool_results})
            tool_rounds += 1
            response = self.client.messages.create(**api_params)

        # Claude still wants tools but hit the round cap — force synthesis without tools
        if response.stop_reason == "tool_use":
            capping_params = {
                **self.base_params,
                "messages": messages,
                "system": system_content
            }
            response = self.client.messages.create(**capping_params)

        for block in response.content:
            if block.type == "text":
                return block.text
        return ""

    def _execute_tool_calls(self, response, tool_manager) -> List[Dict]:
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                try:
                    result = tool_manager.execute_tool(block.name, **block.input)
                except Exception as e:
                    result = f"Tool execution failed: {e}"
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result
                })
        return tool_results
