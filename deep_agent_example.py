import os
import io
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.agents import AgentExecutor, create_react_agent
from langchain.tools import tool
from langchain.memory import ConversationSummaryBufferMemory
from datetime import datetime
from typing import Optional, Type
from pydantic import BaseModel, Field

# Make sure your API key is set as an environment variable:
# export OPENAI_API_KEY="your_openai_api_key_here"
# or export GOOGLE_API_KEY="your_google_api_key_here"

# --- 1. Define Tools with Structured Input (using Pydantic implicitly) ---

# Calculator Tool
@tool
def calculator(expression: str) -> str:
    """Evaluates a mathematical expression and returns the result."""
    try:
        # NOTE: eval() is powerful but can be dangerous with untrusted input.
        # For a real application, use a safer math expression evaluator.
        return str(eval(expression))
    except Exception as e:
        return f"Error: {e}"

# Get Current Datetime Tool
@tool
def get_current_datetime() -> str:
    """Returns the current date and time in YYYY-MM-DD HH:MM:SS format."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Pydantic model for structured input for the write_file tool
class WriteFileToolInput(BaseModel):
    file_path: str = Field(description="The full path to the file to write. e.g., '/path/to/my_document.txt'")
    content: str = Field(description="The content to write into the file.")
    append: bool = Field(default=False, description="If True, append to the file; otherwise, overwrite it. Defaults to False (overwrite).")

# File Writing Tool
@tool(args_schema=WriteFileToolInput)
def write_file_tool(file_path: str, content: str, append: bool = False) -> str:
    """
    Writes content to a specified file.
    If 'append' is True, content is added to the end of the file.
    If 'append' is False (default), the file's existing content is overwritten.
    """
    mode = 'a' if append else 'w'
    try:
        # Using io.open for consistent encoding handling, especially important for varied content.
        with io.open(file_path, mode, encoding='utf-8') as f:
            f.write(content)
        return f"Successfully wrote to {file_path}"
    except Exception as e:
        return f"Error writing to file {file_path}: {e}"

# List of tools the agent can use
tools = [calculator, get_current_datetime, write_file_tool, google_web_search]

# --- 2. Initialize the LLM ---
llm = ChatOpenAI(temperature=0) # Or ChatGoogleGenerativeAI(model="gemini-pro", temperature=0)

# --- 3. Integrate Advanced Memory (ConversationSummaryBufferMemory) ---
# This memory summarizes the conversation, keeping recent messages verbatim.
# The llm_for_summarization is used by the memory to summarize.
memory = ConversationSummaryBufferMemory(
    llm=llm,
    memory_key="chat_history",
    return_messages=True,
    max_token_limit=500 # Adjust based on your LLM's context window and desired history length
)

# --- 4. Create the Prompt Template with Message History Placeholder ---
# We use MessagesPlaceholder for both chat_history and agent_scratchpad.
# The hub.pull("hwchase17/react") prompt already has a good structure,
# but if we want more control or custom system messages with memory, we define it explicitly.
prompt = ChatPromptTemplate.from_messages(
    [
        ("system", "You are a highly capable AI assistant. You have access to various tools to help users. Always think step by step before using a tool."),
        MessagesPlaceholder(variable_name="chat_history"), # For ConversationSummaryBufferMemory
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"), # For agent's thoughts and tool outputs
    ]
)

# --- 5. Create the agent ---
agent = create_react_agent(llm, tools, prompt)

# --- 6. Create the Agent Executor with Memory ---
agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    memory=memory, # Pass the advanced memory object
    verbose=True,
    handle_parsing_errors=True # Basic error handling for tool parsing
)

# --- 7. Run the Agent with various queries to test new capabilities ---
print("--- Agent Query 1: Math and Web Search ---")
result1 = agent_executor.invoke({"input": "What is the capital of Canada and what is 50 * 5?"})
print(f"Result 1: {result1['output']}\n")

print("--- Agent Query 2: Current Date/Time and Web Search ---")
result2 = agent_executor.invoke({"input": "What is the current date and time, and who won the last Super Bowl?"})
print(f"Result 2: {result2['output']}\n")

print("--- Agent Query 3: Follow-up using Memory ---")
# The agent should remember the previous conversation and understand "its" refers to Canada or the Super Bowl winner.
result3 = agent_executor.invoke({"input": "Can you tell me more about its population?"})
print(f"Result 3: {result3['output']}\n")

print("--- Agent Query 4: Write a file ---")
file_content = "This is a test document created by the deep agent. The current time is " + get_current_datetime()
result4 = agent_executor.invoke({"input": f"Please write the following content into a file named 'agent_output.txt': {file_content}"})
print(f"Result 4: {result4['output']}\n")

print("--- Agent Query 5: Append to the file ---")
append_content = "\n\nThis line was appended later."
result5 = agent_executor.invoke({"input": f"Now, please append this text to 'agent_output.txt': {append_content}"})
print(f"Result 5: {result5['output']}\n")

print("--- Agent Query 6: Complex task requiring multiple steps ---")
result6 = agent_executor.invoke({"input": "Summarize the key differences between the ReAct and Plan-and-Execute agent architectures, then save that summary to a file named 'agent_architectures.txt'."})
print(f"Result 6: {result6['output']}\n")
