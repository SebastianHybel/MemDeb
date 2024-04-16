import os
import tkinter as tk
from tkinter import scrolledtext

def load_and_display_filtered_reports(file_name):
    folder_path = 'Chat History'
    file_path = os.path.join(folder_path, file_name)

    try:
        with open(file_path, 'r') as file:
            content = file.read()

        # Initialize the GUI window
        window = tk.Tk()
        window.title("Reports")

        # Create a scrolled text widget
        text_area = scrolledtext.ScrolledText(window, wrap=tk.WORD, width=50, height=60)
        text_area.pack(padx=10, pady=10)
        text_area.insert(tk.INSERT, "**** Agent Reports ****:")

        # Clean the document from 'tool_calls'
        cleaned_content = ""
        while "'tool_calls': [{" in content:
            start_index = content.find("'tool_calls': [{")
            pre_text = content[:start_index]
            content = content[start_index:]
            end_index = content.find("}]") + 2

            # Append the text before 'tool_calls' and skip 'tool_calls' content
            cleaned_content += pre_text
            content = content[end_index:]

        cleaned_content += content  # Add any remaining content after the last 'tool_calls'

        # Convert escaped newlines back to actual newline characters
        cleaned_content = cleaned_content.replace("\\n", "\n")

        # Process the cleaned content to extract and display the reports
        start_indicator = "'content': \"###"
        reports = cleaned_content.split(start_indicator)[1:]  # Skip the first split part if it doesn't start with 'Content: ###'

        for report in reports:
            # Extract up to the next occurrence of 'content': to avoid including subsequent reports
            end_of_report = report.find("'content':")
            if end_of_report != -1:
                report = report[:end_of_report]

            chat_indicator = "\n\n\n\n\n\n\n-------------------- New chat --------------------\n"
            clean_report = chat_indicator + start_indicator + report.strip("\"")
            text_area.insert(tk.INSERT, clean_report + "\n\n")

        # Disable editing in the text area
        text_area.configure(state='disabled')

        # Start the GUI event loop
        window.mainloop()

    except FileNotFoundError:
        print(f"The file {file_name} was not found in {folder_path}.")

# Ensure you have the correct file name
load_and_display_filtered_reports('2024-04-04_TSLA_GPT3.5_V2.txt')