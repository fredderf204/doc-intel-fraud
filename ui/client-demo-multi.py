import gradio as gr
import os
import azure.cosmos.cosmos_client as cosmos_client
from azure.cosmos.partition_key import PartitionKey
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv

load_dotenv()

def application(app_number, app_type, first_name, last_name, address, invoice, receipt):
    # Save application data to Cosmos DB

    HOST = os.getenv('COSHOST')
    MASTER_KEY = os.getenv('COSMASTER_KEY')
    DATABASE_ID = os.getenv('COSDATABASE_ID')
    CONTAINER_ID = os.getenv('COSCONTAINER_ID')

    client = cosmos_client.CosmosClient(HOST, {'masterKey': MASTER_KEY})
    db = client.create_database_if_not_exists(id=DATABASE_ID)
    container = db.create_container_if_not_exists(id=CONTAINER_ID,partition_key=PartitionKey(path='/id', kind='Hash'))

    app_item = {
        'id': app_number,
        'type': app_type,
        'first_name': first_name,
        'last_name': last_name,
        'address': address,
        'invoice': [],
        'receipt': []
    }

    response = container.upsert_item(body=app_item)

    # Save invoice and receipt to Azure Blob Storage
    # Invoice
    in_filename, in_file_extension = os.path.splitext(invoice)
    connection_string = os.getenv('stracc')
    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    blob_name = app_number + "-invoice" + in_file_extension
    blob_client = blob_service_client.get_blob_client(container='invoice', blob=blob_name)
    with open(invoice, 'rb') as data:
        blob_client.upload_blob(data, blob_type="BlockBlob")

    # Receipt
    re_filename, re_file_extension = os.path.splitext(receipt)
    connection_string = os.getenv('stracc')
    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    blob_name = app_number + "-receipt" + re_file_extension
    blob_client = blob_service_client.get_blob_client(container='receipt', blob=blob_name)
    with open(receipt, 'rb') as data:
        blob_client.upload_blob(data, blob_type="BlockBlob")

    # Return data to user
    return "Thank you " + first_name + " " + last_name + " for submitting your " + app_type + " application " + app_number + " ."

demo = gr.Interface(
    fn=application, 
    inputs=[gr.Text(label="Application Number"), gr.Dropdown(choices=["Rebate", "Loan"], label="Type of Application"), gr.Text(label="First Name"), gr.Text(label="Last Name"), "textbox", gr.File(file_types=['.pdf','.jpeg', '.jpg', '.png', '.bmp', '.tiff', '.heif']), gr.File(file_types=['.pdf','.jpeg', '.jpg', '.png', '.bmp', '.tiff', '.heif'])], 
    outputs="textbox",
    title="Sample Customer Rebate Application",
    description="This is a sample application form. Please enter your information, attach your invoice and receipt and submit."
    )
    
demo.launch()