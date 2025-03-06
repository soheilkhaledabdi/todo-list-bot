from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import mysql.connector
from mysql.connector import Error
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_ID = ""
API_HASH = ""
BOT_TOKEN = ""

MYSQL_HOST = "localhost"
MYSQL_USER = "root"
MYSQL_PASSWORD = "sH1382"
MYSQL_DATABASE = "todo_bot"

app = Client("todo_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Database connection
def get_db_connection():
    try:
        connection = mysql.connector.connect(
            host=MYSQL_HOST,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DATABASE
        )
        return connection
    except Error as e:
        logger.error(f"Error connecting to MySQL: {e}")
        return None

# Initialize database
def init_db():
    connection = get_db_connection()
    if connection:
        cursor = connection.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS todos (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id BIGINT,
                task TEXT NOT NULL,
                category VARCHAR(50) DEFAULT 'General',
                priority TINYINT DEFAULT 1,
                completed BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                due_date TIMESTAMP NULL
            )
        """)
        connection.commit()
        cursor.close()
        connection.close()

# Start command
@app.on_message(filters.command("start"))
async def start(client: Client, message: Message):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Add Task", callback_data="add_task")],
        [InlineKeyboardButton("View Tasks", callback_data="list_tasks")],
        [InlineKeyboardButton("Help", callback_data="help")]
    ])
    await message.reply_text(
        "Welcome to Advanced To-Do Bot! 🎯\n"
        "Use the buttons below to manage your tasks:",
        reply_markup=keyboard
    )

# Add task handler
@app.on_callback_query(filters.regex("add_task"))
async def handle_add_task(client: Client, callback: CallbackQuery):
    await callback.answer()  # Answer the callback query first
    await callback.message.reply_text(
        "Please send the task in this format:\n"
        "Task name | Category | Priority (1-3) | Due date (YYYY-MM-DD)\n"
        "Example: Buy groceries | Shopping | 2 | 2025-03-10"
    )

@app.on_message(filters.text)
async def process_task_input(client: Client, message: Message):
    user_id = message.from_user.id
    try:
        parts = [p.strip() for p in message.text.split("|")]
        task = parts[0]
        
        category = parts[1] if len(parts) > 1 else "General"
        priority = int(parts[2]) if len(parts) > 2 else 1
        due_date = parts[3] if len(parts) > 3 else None
        
        if priority not in [1, 2, 3]:
            raise ValueError("Priority must be 1-3")
        
        if due_date:
            datetime.strptime(due_date, "%Y-%m-%d")
        
        connection = get_db_connection()
        if connection:
            cursor = connection.cursor()
            query = """
                INSERT INTO todos (user_id, task, category, priority, due_date)
                VALUES (%s, %s, %s, %s, %s)
            """
            cursor.execute(query, (user_id, task, category, priority, due_date))
            connection.commit()
            
            await message.reply_text(
                f"Task added:\n{task}\nCat: {category}\nPri: {priority}\nDue: {due_date or 'None'}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Back to Menu", callback_data="main_menu")]
                ])
            )
            cursor.close()
            connection.close()
            
    except (ValueError, IndexError) as e:
        await message.reply_text(
            f"Invalid format: {str(e)}\n"
            "Use: Task | Category | Priority (1-3) | Due date (YYYY-MM-DD)"
        )

# List tasks
@app.on_callback_query(filters.regex("list_tasks"))
async def list_tasks(client: Client, callback: CallbackQuery):
    user_id = callback.from_user.id
    connection = get_db_connection()
    
    if connection:
        try:
            cursor = connection.cursor()
            query = """
                SELECT id, task, category, priority, completed, due_date 
                FROM todos 
                WHERE user_id = %s 
                ORDER BY priority DESC, created_at
            """
            cursor.execute(query, (user_id,))
            tasks = cursor.fetchall()
            
            if not tasks:
                await callback.message.edit_text(
                    "No tasks found!",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("Add Task", callback_data="add_task")]
                    ])
                )
                return
                
            response = "📋 Your Tasks:\n\n"
            buttons = []
            for task in tasks:
                status = "✅" if task[4] else "⭕"
                due = f"Due: {task[5].strftime('%Y-%m-%d')}" if task[5] else ""
                response += (
                    f"ID: {task[0]} | {task[1]}\n"
                    f"Cat: {task[2]} | Pri: {task[3]} {status} {due}\n\n"
                )
                buttons.append([
                    InlineKeyboardButton(f"✅ {task[0]}", callback_data=f"done_{task[0]}"),
                    InlineKeyboardButton(f"🗑️ {task[0]}", callback_data=f"delete_{task[0]}")
                ])
            
            buttons.append([InlineKeyboardButton("Back", callback_data="main_menu")])
            await callback.message.edit_text(
                response,
                reply_markup=InlineKeyboardMarkup(buttons)
            )
            
        except Error as e:
            await callback.message.edit_text("Error fetching tasks!")
            logger.error(f"Error fetching tasks: {e}")
        finally:
            cursor.close()
            connection.close()
    await callback.answer()

# Complete task
@app.on_callback_query(filters.regex(r"done_\d+"))
async def complete_task(client: Client, callback: CallbackQuery):
    user_id = callback.from_user.id
    task_id = int(callback.data.split("_")[1])
    
    connection = get_db_connection()
    if connection:
        try:
            cursor = connection.cursor()
            query = "UPDATE todos SET completed = TRUE WHERE id = %s AND user_id = %s"
            cursor.execute(query, (task_id, user_id))
            connection.commit()
            
            await callback.answer("Task marked as completed!")
            await list_tasks(client, callback)
            
        except Error as e:
            await callback.answer("Error completing task!")
            logger.error(f"Error completing task: {e}")
        finally:
            cursor.close()
            connection.close()

# Delete task
@app.on_callback_query(filters.regex(r"delete_\d+"))
async def delete_task(client: Client, callback: CallbackQuery):
    user_id = callback.from_user.id
    task_id = int(callback.data.split("_")[1])
    
    connection = get_db_connection()
    if connection:
        try:
            cursor = connection.cursor()
            query = "DELETE FROM todos WHERE id = %s AND user_id = %s"
            cursor.execute(query, (task_id, user_id))
            connection.commit()
            
            await callback.answer("Task deleted!")
            await list_tasks(client, callback)
            
        except Error as e:
            await callback.answer("Error deleting task!")
            logger.error(f"Error deleting task: {e}")
        finally:
            cursor.close()
            connection.close()

# Main menu
@app.on_callback_query(filters.regex("main_menu"))
async def main_menu(client: Client, callback: CallbackQuery):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Add Task", callback_data="add_task")],
        [InlineKeyboardButton("View Tasks", callback_data="list_tasks")],
        [InlineKeyboardButton("Help", callback_data="help")]
    ])
    await callback.message.edit_text(
        "Main Menu",
        reply_markup=keyboard
    )
    await callback.answer()

# Help
@app.on_callback_query(filters.regex("help"))
async def help_command(client: Client, callback: CallbackQuery):
    await callback.message.edit_text(
        "📖 Help:\n\n"
        "- Add tasks with: Task | Category | Priority (1-3) | Due date\n"
        "- View tasks and manage them with buttons\n"
        "- Priority: 1 (Low), 2 (Medium), 3 (High)\n"
        "- Tasks are sorted by priority and creation date",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Back", callback_data="main_menu")]
        ])
    )
    await callback.answer()

# Run the bot
def main():
    init_db()
    logger.info("Starting Advanced To-Do Bot...")
    app.run()

if __name__ == "__main__":
    main()