from atlassian import Confluence
import json
import weaviate
from weaviate.classes.config import Configure
from weaviate.config import AdditionalConfig,ConnectionConfig
import requests, json

confluence = Confluence(
    url='',
    username='',
    password='')

client = weaviate.connect_to_local(skip_init_checks=True,additional_config=AdditionalConfig(
                connection=ConnectionConfig(
                    session_pool_connections=30,
                    session_pool_maxsize=200,
                    session_pool_max_retries=3,
                ),
                timeout=(60, 180),
            ))

def get_all_pages(confluence, space):
    start = 0
    limit = 100
    _all_pages = []
    while True:
        pages = confluence.get_all_pages_from_space(space, start, limit, status=None, expand=None, content_type='page')
        
        # print(confluence.get_page_by_id(pages.id, expand=None, status=None, version=None))

        _all_pages = _all_pages + pages
        if len(pages) < limit:
            break
        start = start + limit
    return _all_pages

def get_all_pages_data(confluence,space,all_pages):
    cf_dict = []
    for page in all_pages:
        # print(page_json)
        # page = json.loads(page_json)
        # print(page.id)

        cf_page = dict()
        cf_page['title'] = page['title']
        content = confluence.get_page_by_id(page_id=page['id'], expand="body.view", status=None, version=None)
        cf_page['content'] = content['body']['view']['value']
        cf_dict.append(cf_page)
        # content = confluence.get_page_by_title(space=space, title=page['title'])
        # print(json.dumps(page))
    return cf_dict

def create_collection(name):
    questions = client.collections.create(
        name=name,
        vectorizer_config=Configure.Vectorizer.text2vec_ollama(     # Configure the Ollama embedding integration
            api_endpoint="http://host.docker.internal:11434",       # Allow Weaviate from within a Docker container to contact your Ollama instance
            model="nomic-embed-text",                               # The model to use
        ),
        generative_config=Configure.Generative.ollama(              # Configure the Ollama generative integration
            api_endpoint="http://host.docker.internal:11434",       # Allow Weaviate from within a Docker container to contact your Ollama instance
            model="tinyllama",                                       # The model to use
        )
    )

#### Insert objects
def insert_objects(data,collection):
    # resp = requests.get(
    #     "https://raw.githubusercontent.com/weaviate-tutorials/quickstart/main/data/jeopardy_tiny.json"
    # )
    # data = json.loads(resp.text)

    questions = client.collections.get(collection)

    with questions.batch.dynamic() as batch:
        for d in data:
            batch.add_object({
                "title": d["title"],
                "content": d["content"]
            })

    failed_objects = questions.batch.failed_objects # empty
    print(failed_objects)

def delete_collection():
    client.collections.delete('CHASE')

# delete_collection()
all_pages = get_all_pages(confluence=confluence,space='CHASE')
if all_pages:
    cf_dict = get_all_pages_data(confluence=confluence,space='CHASE',all_pages=all_pages)
    if cf_dict and client.is_ready():
        if client.collections.exists('CHASE'):
            print('collection found')
            insert_objects(cf_dict,'CHASE')
            print('confluence data inserted successfully')
        else:
            print('collection not found, creating collection')
            create_collection('CHASE')
            insert_objects(cf_dict,'CHASE')
            print('confluence data inserted successfully')

client.close()    
