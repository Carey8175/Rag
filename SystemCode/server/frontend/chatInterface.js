import { selectedKnowledgebase } from "./sidebar.js";

const backendHost = "http://47.108.135.173";
const backendPort = "18777";

const chatStreamUrl = `${backendHost}:${backendPort}/api/orag/chat_stream`; // Knowledgebase API base URL
const updateChatInfoUrl = `${backendHost}:${backendPort}/api/orag/update/user_chat_information`; // Knowledgebase API base URL
const retrievalUrl = `${backendHost}:${backendPort}/api/orag/retrieval`; // Adjust this according to your API endpoint
const chatContainer = document.getElementById('chat-box');
const sendButton = document.getElementById('send-button');
const modelSelect = document.getElementById('model-select');
const multiTurnBtn = document.getElementById('multi-turn-button');
const modelSettingsButton = document.getElementById('model-settings-button');
const modal = document.getElementById('model-settings-modal');
const closeButton = document.querySelector('.close-button');
const confirmButton = document.getElementById('confirm-button');
const tokenLimit = document.getElementById('token-limit');
const tokenValue = document.getElementById('token-value');
const retrievalButton = document.getElementById('retrival-button');

const modelOptions = [
    "gpt-3.5-turbo", "gpt-3.5-turbo-1106", "gpt-3.5-turbo-0125", "gpt-3.5-turbo-16k",
    "gpt-3.5-turbo-instruct", "gpt-4", "gpt-4o", "gpt-4o-2024-05-13", "gpt-4o-2024-08-06",
    "chatgpt-4o-latest", "gpt-4o-mini", "gpt-4-0613", "gpt-4-turbo-preview", "gpt-4-0125-preview",
    "gpt-4-1106-preview", "gpt-4-vision-preview", "gpt-4-turbo", "gpt-4-turbo-2024-04-09",
    "claude-3-5-sonnet-20240620"
];

let docs = [];
let chatHistory = [];
let selectedModel = null;
let isMultiTurnEnabled = false;
let isRetrievalEnabled = false;
let overallMessages = [];

modelSettingsButton.addEventListener('click', () => {
    modal.style.display = 'block';
});

closeButton.addEventListener('click', () => {
    modal.style.display = 'none';
});

retrievalButton.addEventListener('click', () => {
    isRetrievalEnabled = !isRetrievalEnabled; // Toggle the state
    retrievalButton.classList.toggle('active', isRetrievalEnabled); // Update button style
});

confirmButton.addEventListener('click', () => {
    const apiKey = document.getElementById('api-key').value;
    const baseUrl = document.getElementById('base-url').value;
    selectedModel = modelSelect.value;

    if (apiKey && baseUrl) {
        const data = {};

        fetch(updateChatInfoUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                user_id: getCookie('user_id'),
                api_key: apiKey,
                base_url: baseUrl,
            })
        })
            .then(response => response.json())
            .then(data => {
                console.log('Success:', data);
            })
            .catch(error => {
                console.error('Error:', error);
            });
        localStorage.setItem('api-key', apiKey);
        localStorage.setItem('base-url', baseUrl);
        localStorage.setItem('model-select', selectedModel);

        document.getElementById("model-settings-modal").style.display = "none"; // Hide management interface
        console.log("User ID:", getCookie('user_id'), "API Key:", apiKey, "Base URL:", baseUrl, "Selected Model:", selectedModel);
    } else {
        alert("Please enter your api key and base url")
    }
});

tokenLimit.addEventListener('input', () => {
    tokenValue.textContent = tokenLimit.value;
});

document.addEventListener('DOMContentLoaded', function() {
    loadStoredData();

    // Check if model is selected
    if (!selectedModel) {
        alert("Please select a model before starting the chat.");
    }

    modelSelect.addEventListener('change', function() {
        // selectedModel = this.value;
        selectedModel = this.value;
        console.log("Selected Model:", selectedModel);
    });

    multiTurnBtn.addEventListener('click', toggleMultiTurn);
    modelChoices();

})

document.getElementById("send-button").addEventListener("click", sendMessage);

function loadStoredData() {
    const storedApiKey = localStorage.getItem('api-key');
    const storedBaseUrl = localStorage.getItem('base-url');
    const storedModel = localStorage.getItem('model-select');

    if (storedApiKey) {
        document.getElementById('api-key').value = storedApiKey;
    }
    if (storedBaseUrl) {
        document.getElementById('base-url').value = storedBaseUrl;
    }
    if (storedModel) {
        modelSelect.value = storedModel;
        selectedModel = storedModel;
    }
}

function toggleMultiTurn() {
    isMultiTurnEnabled = !isMultiTurnEnabled;
    multiTurnBtn.classList.toggle('active', isMultiTurnEnabled);
}

// Function to handle sending messages
function sendMessage() {
    const userId = getCookie('user_id');
    const currentMessage = document.getElementById("message-input").value.trim(); // Get the message
    const selectedModel = document.getElementById("model-select").value;

    if (!selectedKnowledgebase) {
        alert("Please select a knowledgebase.");
    }
    if (!selectedModel) {
        alert("Please select a model.");
        return;
    }

    if (!currentMessage) {
        alert("Enter a message.");
        return;
    }

    const kbId = selectedKnowledgebase.kb_id;
    let overallMessages = [];

    // Check if retrieval is enabled
    if (isRetrievalEnabled) {
        // Send the query to the retrieval URL
        const queryData = {
            query: currentMessage,
            user_id: userId,
            kb_id: kbId,
        };

        fetch(retrievalUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(queryData)
        })
        .then(response => response.json())
        .then(data => {
            console.log('Retrieval response:', data);
            const newDocs = data.data;
            const combinedDocs = [...docs, ...newDocs];

            if (combinedDocs.length > 5) {
                docs = combinedDocs.slice(-5); // Keep only the last 5 documents
            } else {
                docs = combinedDocs; // Set docs to combined docs if <= 5
            }

            overallMessages.push({ role: 'system', content: '你是一个数据增强检索系统，系统会给你检索的实际信息，请务必根据检索的实际信息回答用户' });
            docs.forEach(doc => {
                overallMessages.push({ role: 'system', content: doc.content }); // Adjust as needed based on how you want to structure docs
            });

            // Now handle message sending
            handleSendMessage(userId, selectedModel, overallMessages, currentMessage);
        })
        .catch(error => {
            console.error('Error during retrieval:', error);
        });
    } else {
        handleSendMessage(userId, selectedModel, overallMessages, currentMessage);
    }
}


// Function to handle sending messages based on mode
function handleSendMessage(userId, selectedModel, overallMessages, currentMessage) {
    // In multi-turn mode, add the message to the queue
    if (isMultiTurnEnabled) {
        chatHistory.push({ role: 'user', content: overallMessages }); // Add message to queue
        addMessageToChat('user', currentMessage);
        console.log("Message added to queue:", overallMessages);
        sendToBackend(userId, selectedModel, overallMessages.concat(chatHistory));
    } else {
        // Single-turn mode: Send only the current message immediately
        addMessageToChat('user', currentMessage);
        sendToBackend(userId, selectedModel, overallMessages.concat([{'role': 'user', 'content': currentMessage}]));
    }
    document.getElementById("message-input").value = '';
}

// Function to connect to chatStream mode
async function sendToBackend(userId, model, messageList) {
    sendButton.disabled = true;
    // Send a request to chatStreamUrl
    const formData = new FormData();

    formData.append("user_id", userId);
    formData.append("messages", JSON.stringify(messageList));
    formData.append("model", model);
    console.log("FormData being sent:", Array.from(formData.entries()));

    try {
        const response = await fetch(chatStreamUrl, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let done = false;

        while (!done) {
            const {value, done: readerDone} = await reader.read();
            done = readerDone;

            if (value) {
                const chunk = decoder.decode(value, {stream: true});
                // Append each chunk to the chat container
                chatContainer.innerHTML += chunk;
                chatContainer.scrollTop = chatContainer.scrollHeight;
            }
        }
    }catch (error){
        chatContainer.innerHTML = 'Error: ' + error.message;
    }
    sendButton.disabled = false;
}

// Function to display messages in the chat box
function addMessageToChat(role, message) {
    const chatBox = document.getElementById("chat-box");
    const newMessage = document.createElement("div");
    newMessage.classList.add(role);  // Add class based on role (e.g., 'user' or 'assistant')
    newMessage.textContent = message;
    chatBox.appendChild(newMessage);  // Append the new message to chat display
}

function modelChoices() {
    modelSelect.innerHTML = '';
    modelOptions.forEach(model => {
        const option = document.createElement('option');
        option.value = model;
        option.textContent = model;
        modelSelect.appendChild(option);
    })

    if (modelOptions.length > 0) {
        modelSelect.value = modelOptions[0];
        selectedModel = modelOptions[0];
    }
}

document.getElementById("message-input").addEventListener("keydown", function(e) {
    if (e.key === "Enter") {
        sendMessage();
    }
});

document.getElementById("new-chat-button").addEventListener("click", function() {
    chatHistory = [];  // Reset chat history
    document.getElementById("chat-box").innerHTML = '';  // Clear the chat display
    document.getElementById("message-input").value = '';  // Clear the input field
    alert("New conversation started!");  // Optional alert to notify the user
});

export function goToChatInterface(knowledgebase) {
    document.getElementById("chat-interface").style.display = "block"; // Show chat interface
    document.getElementById("database-management").style.display = "none"; // Hide management interface
    console.log(`Switched to chat for knowledgebase: ${knowledgebase.kb_name}`);
}

// Get cookie value by name
function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
    return null;
}