from flask import Flask, request, jsonify
import requests
import os
import openai
from dotenv import load_dotenv
import time

# Load environment variables from .env file
load_dotenv()

# Set OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")
google_api_key = os.getenv("GOOGLE_API_KEY")
cse_id = os.getenv("CSE_ID")
assistantId = os.getenv("ASSISTANT_ID")

# Create a client instance
client = openai.Client()

app = Flask(__name__)

def search_google(query, api_key, cse_id, **kwargs):
    # Perform the search
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        'q': query,
        'key': api_key,
        'cx': cse_id,
    }
    params.update(kwargs)
    response = requests.get(url, params=params)
    results = response.json()

    # Extract relevant information
    extracted_data = []

    if 'items' in results:
        for item in results['items']:
            title = item.get('title')
            link = item.get('link')
            snippet = item.get('snippet')

            extracted_data.append({
                'title': title,
                'link': link,
                'snippet': snippet
            })

    return extracted_data

def getAssistantSearchResponse(assistant_id, prompt, thread_id=None):
    if thread_id is None:
        # Create a new thread if thread_id is not provided
        thread = client.beta.threads.create()
        thread_id = thread.id
    else:
        # Use the provided thread_id
        thread_id = thread_id

    message = client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content= prompt,
    )

    run = client.beta.threads.runs.create(
        thread_id=thread_id,
        assistant_id=assistant_id,
        )

    while True:  # Change to an infinite loop to continually check for completion
        run = client.beta.threads.runs.retrieve(
            thread_id=thread_id,
            run_id=run.id
        )
        print(run.status)
        if run.status == "completed":
            break  # Exit the loop once the run is completed
        elif run.status == "failed":
            print(run)
        elif run.status == 'requires_action':
            required_actions = run.required_action.submit_tool_outputs.model_dump()
            tool_outputs = []
            import json
            for action in required_actions["tool_calls"]:
                func_name = action['function']['name']
                arguments = json.loads(action['function']['arguments'])
                print(func_name)
                print(arguments)

                if func_name == "search_google":
                    output = search_google(arguments['query'], google_api_key, cse_id)
                    output = '\n'.join([f"Title: {item['title']}\nLink: {item['link']}\nDescription: {item['snippet']}\n" for item in output])
                    print("output", output)
                    tool_outputs.append({
                        "tool_call_id": action['id'],
                        "output": output
                    })
                else:
                    raise ValueError(f"Unknown function: {func_name}")
            
            client.beta.threads.runs.submit_tool_outputs(
                thread_id=thread_id,
                run_id=run.id,
                tool_outputs=tool_outputs
            )
        else:
            time.sleep(0.5)
    
    messages = client.beta.threads.messages.list(
        thread_id=thread_id
    )

    return messages.data[0].content[0].text.value


@app.route('/get-response', methods=['POST'])
def get_response():
    data = request.json
    prompt = data.get("prompt")
    thread_id = data.get("thread_id")

    if not prompt:
        return jsonify({"error": "No prompt provided"}), 400

    response = getAssistantSearchResponse(assistantId, prompt, thread_id)

    return jsonify({"response": response})

@app.route('/', methods=['GET'])
def hello():
    return "Hello, it's working"


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))

