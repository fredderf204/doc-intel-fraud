import gradio as gr
import os
import azure.cosmos.cosmos_client as cosmos_client
from azure.cosmos.partition_key import PartitionKey
from dotenv import load_dotenv

load_dotenv()

def application(app_number):
    # Retreive application data from Cosmos DB
    HOST = os.getenv('COSHOST')
    MASTER_KEY = os.getenv('COSMASTER_KEY')
    DATABASE_ID = os.getenv('COSDATABASE_ID')
    CONTAINER_ID = os.getenv('COSCONTAINER_ID')

    client = cosmos_client.CosmosClient(HOST, {'masterKey': MASTER_KEY})
    db = client.create_database_if_not_exists(id=DATABASE_ID)
    container = db.get_container_client(CONTAINER_ID)
    query = 'SELECT * FROM c WHERE c.id = ' + '"' + app_number + '"'
    items = container.query_items(
        query=query,
        enable_cross_partition_query=True
    )
    
    for i in items:
        return i.get('first_name'), i.get('last_name'), i.get('address'), i.get('invoice'), i.get('receipt'), i.get('comparison')

demo = gr.Interface(
    fn=application,
    inputs=[gr.Text(label="Application Number")],
    outputs=[gr.Text(label="First Name"), gr.Text(label="Last Name"), gr.Text(label="Address"), gr.Text(label="Invoice"), gr.Text(label="Receipt"), gr.Text(label="comparison")],
    title="Sample Processor Application",
    description="This is a sample application for a processors to assess the rebate application. Enter the application number to retrieve the application data."
    )
    
demo.launch()