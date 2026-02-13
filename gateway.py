#!/usr/bin/env python3
"""Custom Telegram Gateway for Vantage Bot"""
import json
import logging
import re
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
import httpx

from config import (
    TELEGRAM_TOKEN, VLLM_URL, BACKEND_API, DEFAULT_PROJECT,
    MEDIA_INBOX, MODEL_NAME, MODEL_TEMPERATURE, MODEL_MAX_TOKENS, LOG_LEVEL
)
from prompts import SYSTEM_PROMPT
from tools import TOOLS, execute_tool

# Setup logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def get_enriched_context(project_slug: str) -> str:
    """Fetch enriched context from backend API"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{BACKEND_API}/projects/{project_slug}/chat/context")
            if response.status_code == 200:
                return response.json().get("context", "")
            else:
                logger.warning(f"Failed to fetch context: {response.status_code}")
                return ""
        except Exception as e:
            logger.error(f"Error fetching context: {e}")
            return ""


async def call_vllm(messages: list, tools: list = None) -> dict:
    """Call vLLM server with messages and optional tools"""
    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "temperature": MODEL_TEMPERATURE,
        "max_tokens": MODEL_MAX_TOKENS
    }

    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    logger.debug(f"Calling vLLM with {len(messages)} messages and {len(tools) if tools else 0} tools")

    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            response = await client.post(VLLM_URL, json=payload)
            response.raise_for_status()
            result = response.json()
            logger.debug(f"vLLM response: {json.dumps(result, indent=2)}")
            return result
        except Exception as e:
            logger.error(f"vLLM call failed: {e}")
            raise


def strip_think_tags(text: str) -> str:
    """Remove <think> tags and their contents from text"""
    if not text:
        return ""
    # Remove everything from <think> to </think>
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    # Clean up any remaining stray tags
    text = re.sub(r'</?think>', '', text)
    return text.strip()


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming Telegram messages"""
    user_message = update.message.text
    chat_id = update.effective_chat.id

    logger.info(f"Received message from {chat_id}: {user_message}")

    # Send typing indicator
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    try:
        # Get enriched context from backend
        enriched_context = await get_enriched_context(DEFAULT_PROJECT)

        # Build message history with enriched context
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": f"PROJECT CONTEXT:\n{enriched_context}"},
            {"role": "user", "content": user_message}
        ]

        # Call vLLM with tools
        response = await call_vllm(messages, TOOLS)

        # Check if LLM wants to call tools
        choice = response["choices"][0]
        message = choice["message"]

        if message.get("tool_calls"):
            # Execute each tool call
            logger.info(f"LLM requested {len(message['tool_calls'])} tool calls")
            messages.append(message)

            for tool_call in message["tool_calls"]:
                tool_name = tool_call["function"]["name"]
                arguments = json.loads(tool_call["function"]["arguments"])

                logger.info(f"Executing tool: {tool_name} with args: {arguments}")

                # Execute tool
                tool_result = execute_tool(tool_name, arguments)
                logger.info(f"Tool result: {tool_result}")

                # Add tool result to messages
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "name": tool_name,
                    "content": json.dumps(tool_result)
                })

            # Call LLM again with tool results to get final response
            await context.bot.send_chat_action(chat_id=chat_id, action="typing")
            final_response = await call_vllm(messages, TOOLS)
            final_message = final_response["choices"][0]["message"]["content"]
        else:
            # No tool calls, use direct response
            final_message = message["content"]

        # Strip <think> tags if present
        final_message = strip_think_tags(final_message)

        if not final_message or final_message.isspace():
            final_message = "I processed your request but have no response to show."
            logger.warning("Empty response after stripping think tags")

        # Send response to user
        await update.message.reply_text(final_message, parse_mode="HTML")
        logger.info(f"Sent response: {final_message[:100]}...")

    except Exception as e:
        error_msg = f"Error processing message: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await update.message.reply_text("Sorry, I encountered an error processing your request.")


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle document uploads (PDFs, etc.)"""
    chat_id = update.effective_chat.id
    document = update.message.document

    logger.info(f"Received document: {document.file_name}")

    try:
        # Download file to media inbox
        MEDIA_INBOX.mkdir(parents=True, exist_ok=True)
        file = await context.bot.get_file(document.file_id)
        file_path = MEDIA_INBOX / document.file_name
        await file.download_to_drive(file_path)

        logger.info(f"Saved file to: {file_path}")

        await update.message.reply_text(f"Received {document.file_name}. Processing...")

        # If it's a PDF, assume it's an RFP and trigger processing
        if file_path.suffix.lower() == '.pdf':
            # Simulate user message "Process this RFP"
            update.message.text = "Process this RFP document"
            await handle_message(update, context)
        else:
            await update.message.reply_text(
                f"File saved. Use a command to tell me what to do with it (e.g., 'complete task 4')."
            )

    except Exception as e:
        error_msg = f"Error handling document: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await update.message.reply_text("Sorry, I encountered an error handling your file.")


def main():
    """Start the bot"""
    logger.info("Starting Vantage Telegram Gateway...")
    logger.info(f"Using model: {MODEL_NAME}")
    logger.info(f"Backend API: {BACKEND_API}")
    logger.info(f"vLLM URL: {VLLM_URL}")
    logger.info(f"Default project: {DEFAULT_PROJECT}")

    # Create application
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Add handlers
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    # Start bot
    logger.info("Bot started successfully. Ready to receive messages.")
    application.run_polling()


if __name__ == "__main__":
    main()
