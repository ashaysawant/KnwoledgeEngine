import weaviate
from weaviate.classes.config import Configure
from weaviate.config import AdditionalConfig,ConnectionConfig
import requests, json
import torch
from transformers import pipeline

####### Create Collection
def create_collection():
    questions = client.collections.create(
        name="Question",
        vectorizer_config=Configure.Vectorizer.text2vec_ollama(     # Configure the Ollama embedding integration
            api_endpoint="http://host.docker.internal:11434",       # Allow Weaviate from within a Docker container to contact your Ollama instance
            model="nomic-embed-text",                               # The model to use
        ),
        generative_config=Configure.Generative.ollama(              # Configure the Ollama generative integration
            api_endpoint="http://host.docker.internal:11434",       # Allow Weaviate from within a Docker container to contact your Ollama instance
            model="llama3.2",                                       # The model to use
        )
    )

#### Insert objects
def insert_objects():
    resp = requests.get(
        "https://raw.githubusercontent.com/weaviate-tutorials/quickstart/main/data/jeopardy_tiny.json"
    )
    data = json.loads(resp.text)

    questions = client.collections.get("Question")

    with questions.batch.dynamic() as batch:
        for d in data:
            batch.add_object({
                "answer": d["Answer"],
                "question": d["Question"],
                "category": d["Category"],
            })

    failed_objects = questions.batch.failed_objects # empty
    print(failed_objects)

def fetch_objects():
    questions = client.collections.get("CHASE")
    response = questions.query.fetch_objects()

    for o in response.objects:
        print(o.properties)

def fetch_vector():
    questions = client.collections.get("CHASE")
    response = questions.query.fetch_objects(
        include_vector=True,
        limit=1
    )

    print(response.objects[0].vector["default"])

######Semantic Search
def search(query):
    questions = client.collections.get("CHASE")
    response = questions.query.near_text(
        query=query,
        limit=2
    )

    # response = questions.query.hybrid(
    # query=query,  # The model provider integration will automatically vectorize the query
    # limit=2
    # )
    # print(response)
    for obj in response.objects:
        return json.dumps(obj.properties, indent=2)

def retrieveAndGenerate():
    questions = client.collections.get("CHASE")
    response = questions.generate.near_text(
        query="can you evaluate chase saffire credit card?",
        limit=2,
        grouped_task="Write a summary based on the query."
    )
    print(response.generated)  # Inspect the generated text

def generate_answer(query,context):
    pipe = pipeline("text-generation", model="TinyLlama/TinyLlama-1.1B-Chat-v1.0", torch_dtype=torch.bfloat16, device_map="auto")

    # We use the tokenizer's chat template to format each message - see https://huggingface.co/docs/transformers/main/en/chat_templating
    messages = [
        {
            "role": "system",
            "content": "You are an financial expert with knowledge on credit cards",
        },
        {"role": "user", "content": query,"context":context},
    ]
    prompt = pipe.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    print(prompt)
    outputs = pipe(prompt, max_new_tokens=2560, do_sample=True, temperature=0.7, top_k=50, top_p=0.95)
    return outputs[0]["generated_text"]

client = weaviate.connect_to_local(skip_init_checks=True,additional_config=AdditionalConfig(
                connection=ConnectionConfig(
                    session_pool_connections=30,
                    session_pool_maxsize=200,
                    session_pool_max_retries=3,
                ),
                timeout=(3600, 3600),
            ))
print(client.is_ready())  # Should print: `True`
# fetch_objects()
# fetch_vector()
# create_collection()
# insert_objects()
query = "chase saffire credit card"
context = search(query)
# print(context)
# retrieveAndGenerate()
print(generate_answer(query=query,context=context))
client.close()  # Free up resources




