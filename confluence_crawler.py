from atlassian import Confluence
import weaviate
from weaviate.classes.config import Configure
from weaviate.config import AdditionalConfig,ConnectionConfig
import os
import glob
import docx2txt
from pypdf import PdfReader

confluence = Confluence(
    url=os.environ['confluenceURL'],
    username=os.environ['confluenceUserID'],
    password=os.environ['confluencePass'] )

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
        _all_pages = _all_pages + pages
        if len(pages) < limit:
            break
        start = start + limit
    return _all_pages

def load_attachments(cf_dict):
    for word_file in glob.glob("./Data/*.docx"):
        text = docx2txt.process(word_file)
        cf_page = dict()
        cf_page['title'] = os.path.basename(word_file) 
        cf_page['content'] = text
        cf_dict.append(cf_page)
    for pdf_file in glob.glob("./Data/*.pdf"):
        reader = PdfReader(pdf_file)
        l = []
        for page in reader.pages:
            # extracting text from page
            l.append(page.extract_text())
        cf_page = dict()
        cf_page['title'] = os.path.basename(pdf_file) 
        cf_page['content'] = ''.join(l)
        cf_dict.append(cf_page)
    return cf_dict

def download_attachments(confluence,pageId):
    attachments_container = confluence.get_attachments_from_content(page_id=pageId, start=0, limit=500)
    # print(attachments_container)
    attachments = attachments_container['results']
    if attachments:
        resp = confluence.download_attachments_from_page(pageId, path='./Data')
        if resp['attachments downloaded'] > 0:
            return True
    return False

def delete_attachments():
    for myfile in glob.glob("./Data/*"):
        # If file exists, delete it.
        if os.path.isfile(myfile):
            os.remove(myfile)


def get_all_pages_data(confluence,space,all_pages):
    cf_dict = []
    attachments_present = False
    for page in all_pages:
        cf_page = dict()
        cf_page['title'] = page['title']
        content = confluence.get_page_by_id(page_id=page['id'], expand="body.view", status=None, version=None)
        cf_page['content'] = content['body']['view']['value']
        cf_dict.append(cf_page)
        if (download_attachments(confluence=confluence,pageId=page['id'])):
            attachments_present = True
    if attachments_present:
        cf_dict = load_attachments(cf_dict)
        delete_attachments()
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
    print(cf_dict)
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
