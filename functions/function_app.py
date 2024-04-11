import azure.functions as func
import logging
import re
import json
import os
from openai import AzureOpenAI
from azure.core.credentials import AzureKeyCredential
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.storage.blob import BlobClient
from azure.cosmos import CosmosClient, PartitionKey

app = func.FunctionApp()

@app.blob_trigger(arg_name="inblobtrig", path="invoice/{name}", connection="mfdocintell_STORAGE")
@app.blob_output(arg_name="outputblob", path="processed/{name}", connection="mfdocintell_STORAGE")

def invoice(inblobtrig: func.InputStream, outputblob: func.Out[str]):
    
    # Extract the invoice number from the blob name
    application_number = re.search(r'^invoice\/(\d+)-invoice\.pdf$', inblobtrig.name).group(1)
    blob_name = re.search(r'/(\d+-invoice\.pdf)$', inblobtrig.name).group(1)

    # Future feature: Check document type using Document Intelligence Custom Classification model. If not invoice, alert ops team.
    # https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/concept-custom-classifier?view=doc-intel-4.0.0

    # Call the AI model to extract the invoice data
    endpoint = os.getenv("docintell_endpoint")
    key = os.getenv("docintell_key")

    document_analysis_client = DocumentAnalysisClient(endpoint=endpoint, credential=AzureKeyCredential(key))
    poller = document_analysis_client.begin_analyze_document_from_url("prebuilt-invoice", inblobtrig.uri)
    invoices = poller.result()

    invoice_data = {}

    # Pre generated invoice URI after its been processed
    storage_config_str = os.getenv("mfdocintell_STORAGE")
    key_value_pairs = storage_config_str.split(';')
    storage_account_name = key_value_pairs[1].split('=')[1]
    storage_account_suffix = key_value_pairs[3].split('=')[1]
    invoice_data["invoice_uri"] = "https://" + storage_account_name + ".blob." + storage_account_suffix + "/processed/" + blob_name
    
    invoice_data["content"] = str(invoices.content)

    # Loop through the extracted invoice data and save it to a dictionary
    for idx, invoice in enumerate(invoices.documents):
        vendor_name = invoice.fields.get("VendorName")
        if vendor_name:
            invoice_data["vendor_name"] = vendor_name.value
            invoice_data["vendor_name_confidence"] = vendor_name.confidence
 
        vendor_address = invoice.fields.get("VendorAddress")
        if vendor_address:
            invoice_data["vendor_address"] = str(vendor_address.value)
            invoice_data["vendor_address_confidence"] = vendor_address.confidence

        vendor_address_recipient = invoice.fields.get("VendorAddressRecipient")
        if vendor_address_recipient:
            invoice_data["vendor_address_recipient"] = vendor_address_recipient.value
            invoice_data["vendor_address_recipient_confidence"] = vendor_address_recipient.confidence

        customer_name = invoice.fields.get("CustomerName")
        if customer_name:
            invoice_data["customer_name"] = customer_name.value
            invoice_data["customer_name_confidence"] = customer_name.confidence

        customer_id = invoice.fields.get("CustomerId")
        if customer_id:
            invoice_data["customer_id"] = customer_id.value
            invoice_data["customer_id_confidence"] = customer_id.confidence

        customer_address = invoice.fields.get("CustomerAddress")
        if customer_address:
            invoice_data["customer_address"] = customer_address.value
            invoice_data["customer_address_confidence"] = customer_address.confidence

        customer_address_recipient = invoice.fields.get("CustomerAddressRecipient")
        if customer_address_recipient:
            invoice_data["customer_address_recipient"] = str(customer_address_recipient.value)
            invoice_data["customer_address_recipient_confidence"] = customer_address_recipient.confidence

        invoice_id = invoice.fields.get("InvoiceId")
        if invoice_id:
            invoice_data["invoice_id"] = invoice_id.value
            invoice_data["invoice_id_confidence"] = invoice_id.confidence

        invoice_date = invoice.fields.get("InvoiceDate")
        if invoice_date:
            invoice_data["invoice_date"] = invoice_date.value.strftime("%B %d, %Y")
            invoice_data["invoice_date_confidence"] = invoice_date.confidence

        invoice_total = invoice.fields.get("InvoiceTotal")
        if invoice_total:
            invoice_data["invoice_total"] = str(invoice_total.value.code) + " $" + str(invoice_total.value.amount)
            invoice_data["invoice_total_confidence"] = invoice_total.confidence

        due_date = invoice.fields.get("DueDate")
        if due_date:
            invoice_data["due_date"] = due_date.value
            invoice_data["due_date_confidence"] = due_date.confidence

        purchase_order = invoice.fields.get("PurchaseOrder")
        if purchase_order:
            invoice_data["purchase_order"] = purchase_order.value
            invoice_data["purchase_order_confidence"] = purchase_order.confidence

        billing_address = invoice.fields.get("BillingAddress")
        if billing_address:
            invoice_data["billing_address"] = str(billing_address.value)
            invoice_data["billing_address_confidence"] = billing_address.confidence

        billing_address_recipient = invoice.fields.get("BillingAddressRecipient")
        if billing_address_recipient:
            invoice_data["billing_address_recipient"] = billing_address_recipient.value
            invoice_data["billing_address_recipient_confidence"] = billing_address_recipient.confidence

        shipping_address = invoice.fields.get("ShippingAddress")
        if shipping_address:
            invoice_data["shipping_address"] = shipping_address.value
            invoice_data["shipping_address_confidence"] = shipping_address.confidence

        shipping_address_recipient = invoice.fields.get("ShippingAddressRecipient")
        if shipping_address_recipient: 
            invoice_data["shipping_address_recipient"] = shipping_address_recipient.value
            invoice_data["shipping_address_recipient_confidence"] = shipping_address_recipient.confidence

        items = {}
        for idx, item in enumerate(invoice.fields.get("Items").value):
            item_description = item.value.get("Description")
            if item_description:
                items[f"item_{idx}_description"] = item_description.value
                items[f"item_{idx}_description_confidence"] = item_description.confidence

            item_quantity = item.value.get("Quantity")
            if item_quantity:
                items[f"item_{idx}_quantity"] = item_quantity.value
                items[f"item_{idx}_quantity_confidence"] = item_quantity.confidence

            unit = item.value.get("Unit")
            if unit:
                items[f"item_{idx}_unit"] = unit.value
                items[f"item_{idx}_unit_confidence"] = unit.confidence

            unit_price = item.value.get("UnitPrice")
            if unit_price:
                items[f"item_{idx}_unit_price"] = str(unit_price.value.code) + " $" + str(unit_price.value.amount)
                items[f"item_{idx}_unit_price_confidence"] = unit_price.confidence

            product_code = item.value.get("ProductCode")
            if product_code:
                items[f"item_{idx}_product_code"] = product_code.value
                items[f"item_{idx}_product_code_confidence"] = product_code.confidence

            item_date = item.value.get("Date")
            if item_date:
                items[f"item_{idx}_date"] = item_date.value
                items[f"item_{idx}_date_confidence"] = item_date.confidence

            tax = item.value.get("Tax")
            if tax:
                items[f"item_{idx}_tax"] = str(tax.value.code) + " $" + str(tax.value.amount)
                items[f"item_{idx}_tax_confidence"] = tax.confidence

            amount = item.value.get("Amount")
            if amount:
                items[f"item_{idx}_amount"] = str(amount.value.code) + " $" + str(amount.value.amount)
                items[f"item_{idx}_amount_confidence"] = amount.confidence

        subtotal = invoice.fields.get("SubTotal")
        if subtotal:
            invoice_data["subtotal"] = str(subtotal.value.code) + " $" + str(subtotal.value.amount)
            invoice_data["subtotal_confidence"] = subtotal.confidence

        total_tax = invoice.fields.get("TotalTax")
        if total_tax:
            invoice_data["total_tax"] = str(total_tax.value.code) + " $" + str(total_tax.value.amount)
            invoice_data["total_tax_confidence"] = total_tax.confidence
        
        previous_unpaid_balance = invoice.fields.get("PreviousUnpaidBalance")
        if previous_unpaid_balance:
            invoice_data["previous_unpaid_balance"] = previous_unpaid_balance.value
            invoice_data["previous_unpaid_balance_confidence"] = previous_unpaid_balance.confidence

        amount_due = invoice.fields.get("AmountDue")
        if amount_due:
            invoice_data["amount_due"] = amount_due.value
            invoice_data["amount_due_confidence"] = amount_due.confidence
        
        service_start_date = invoice.fields.get("ServiceStartDate")
        if service_start_date:
            invoice_data["service_start_date"] = service_start_date.value
            invoice_data["service_start_date_confidence"] = service_start_date.confidence

        service_end_date = invoice.fields.get("ServiceEndDate")
        if service_end_date:
            invoice_data["service_end_date"] = service_end_date.value
            invoice_data["service_end_date_confidence"] = service_end_date.confidence

        service_address = invoice.fields.get("ServiceAddress")
        if service_address:
            invoice_data["service_address"] = service_address.value
            invoice_data["service_address_confidence"] = service_address.confidence

        service_address_recipient = invoice.fields.get("ServiceAddressRecipient")
        if service_address_recipient:
            invoice_data["service_address_recipient"] = service_address_recipient.value
            invoice_data["service_address_recipient_confidence"] = service_address_recipient.confidence

        remittance_address = invoice.fields.get("RemittanceAddress")
        if remittance_address:
            invoice_data["remittance_address"] = remittance_address.value
            invoice_data["remittance_address_confidence"] = remittance_address.confidence

        remittance_address_recipient = invoice.fields.get("RemittanceAddressRecipient")
        if remittance_address_recipient:
            invoice_data["remittance_address_recipient"] = remittance_address_recipient.value
            invoice_data["remittance_address_recipient_confidence"] = remittance_address_recipient.confidence

        invoice_data["items"] = items

    invoice_data["invoice_status"] = "Invoice processed successfully." 

    # Save extracted invoice data to Cosmos DB
    #doc = next((x for x in inputDocument if x["id"] == application_number), None)
    #doc.data["invoice"] = invoice_data

    #if doc.get("receipt"):
    #    doc.data["receipt"] = doc.get("receipt")

    # Get cosmosdb record and replace the updated document to Cosmos DB if _etag matches
    client = CosmosClient.from_connection_string(os.getenv("cosmosdb_config"))
    database = client.get_database_client("ToDoList")
    container = database.get_container_client("docs")
    doc = container.read_item(item=application_number, partition_key=application_number)
    item_etag = doc["_etag"]
    doc["invoice"] = invoice_data
    try:
        container.replace_item(doc, doc, if_match=item_etag)
    except:
        doc = container.read_item(item=application_number, partition_key=application_number)
        item_etag = doc["_etag"]
        doc["invoice"] = invoice_data
        container.replace_item(doc, doc, if_match=item_etag)

    # Save the updated document to Cosmos DB if _etag matches
    #####
    #outputDocument.set(doc)

    # Move the blob to the processed container
    outputblob.set(inblobtrig.read())

    # delete the original blob
    blob_name = re.search(r'/(\d+-invoice\.pdf)$', inblobtrig.name).group(1)
    blob_client = BlobClient.from_connection_string(os.getenv("mfdocintell_STORAGE"), "invoice", blob_name)
    blob_client.delete_blob()

    return

@app.blob_trigger(arg_name="recblobtrig", path="receipt/{name}", connection="mfdocintell_STORAGE")
@app.blob_output(arg_name="outputblob", path="processed/{name}", connection="mfdocintell_STORAGE")

def receipt(recblobtrig: func.InputStream, outputblob: func.Out[str]):
    
    # Extract the receipt number from the blob name
    application_number = re.search(r'^receipt\/(\d+)-receipt\.[A-Za-z]+$', recblobtrig.name).group(1)
    blob_name = re.search(r'/(\d+-receipt\.[A-Za-z]+)$', recblobtrig.name).group(1)

    # Future feature: Check document type using Document Intelligence Custom Classification model. If not receipt, alert ops team.
    # https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/concept-custom-classifier?view=doc-intel-4.0.0

    # Call the AI model to extract the receipt data
    endpoint = os.getenv("docintell_endpoint")
    key = os.getenv("docintell_key")

    document_analysis_client = DocumentAnalysisClient(endpoint=endpoint, credential=AzureKeyCredential(key))
    poller = document_analysis_client.begin_analyze_document_from_url("prebuilt-receipt", recblobtrig.uri)
    receipts = poller.result()

    receipt_data = {}

    # Pre generated receipt URI after its been processed
    storage_config_str = os.getenv("mfdocintell_STORAGE")
    key_value_pairs = storage_config_str.split(';')
    storage_account_name = key_value_pairs[1].split('=')[1]
    storage_account_suffix = key_value_pairs[3].split('=')[1]
    receipt_data["receipt_uri"] = "https://" + storage_account_name + ".blob." + storage_account_suffix + "/processed/" + blob_name
    
    receipt_data["content"] = str(receipts.content)

    # Loop through the extracted receipt data and save it to a dictionary
    for idx, receipt in enumerate(receipts.documents):
        merchant_name = receipt.fields.get("MerchantName")
        if merchant_name:
            receipt_data["merchant_name"] = merchant_name.value
            receipt_data["merchant_name_confidence"] = merchant_name.confidence
 
        transaction_date = receipt.fields.get("TransactionDate")
        if transaction_date:
            receipt_data["transaction_date"] = transaction_date.value.strftime("%B %d, %Y")
            receipt_data["transaction_date_confidence"] = transaction_date.confidence

        if receipt.fields.get("Items"):
            items = {}
            for idx, item in enumerate(receipt.fields.get("Items").value):
                item_description = item.value.get("Description")
                if item_description:
                    items[f"item_{idx}_description"] = item_description.value
                    items[f"item_{idx}_description_confidence"] = item_description.confidence

                item_quantity = item.value.get("Quantity")
                if item_quantity:
                    items[f"item_{idx}_quantity"] = item_quantity.value
                    items[f"item_{idx}_quantity_confidence"] = item_quantity.confidence

                item_price = item.value.get("Price")
                if item_price:
                    items[f"item_{idx}_price"] = str(item_price) + " $" + str(item_price.value.amount)
                    items[f"item_{idx}_price_confidence"] = item_price.confidence

                item_total_price = item.value.get("TotalPrice")
                if item_total_price:
                    items[f"item_{idx}_total_price"] = str(item_total_price.value)
                    items[f"item_{idx}_total_price_confidence"] = item_total_price.confidence

        subtotal = receipt.fields.get("Subtotal")
        if subtotal:
            receipt_data["subtotal"] = str(subtotal.value)
            receipt_data["subtotal_confidence"] = subtotal.confidence

        tax = receipt.fields.get("TotalTax")
        if tax:
            receipt_data["total_tax"] = str(tax.value)
            receipt_data["total_tax_confidence"] = tax.confidence
        
        tip = receipt.fields.get("Tip")
        if tip:
            receipt_data["tip"] = str(tip.value)
            receipt_data["tip_confidence"] = tip.confidence

        total = receipt.fields.get("Total")
        if total:
            receipt_data["total"] = str(total.value)
            receipt_data["total_confidence"] = total.confidence

        receipt_data["items"] = items

    receipt_data["receipt_status"] = "Receipt processed successfully." 

    # Save extracted receipt data to Cosmos DB
    #doc = next((x for x in recinputDocument if x["id"] == application_number), None)
    #doc.data["receipt"] = receipt_data

    #if doc.get("invoice"):
    #    doc.data["invoice"] = doc.get("invoice")

    #recoutputDocument.set(doc)

    # Get cosmosdb record and replace the updated document to Cosmos DB if _etag matches
    client = CosmosClient.from_connection_string(os.getenv("cosmosdb_config"))
    database = client.get_database_client("ToDoList")
    container = database.get_container_client("docs")
    doc = container.read_item(item=application_number, partition_key=application_number)
    item_etag = doc["_etag"]
    doc["receipt"] = receipt_data
    try:
        container.replace_item(doc, doc, if_match=item_etag)
    except:
        doc = container.read_item(item=application_number, partition_key=application_number)
        item_etag = doc["_etag"]
        doc["receipt"] = receipt_data
        container.replace_item(doc, doc, if_match=item_etag)

    # Move the blob to the processed container
    outputblob.set(recblobtrig.read())

    # delete the original blob
    blob_name = re.search(r'/(\d+-receipt\.[A-Za-z]+)$', recblobtrig.name).group(1)
    blob_client = BlobClient.from_connection_string(os.getenv("mfdocintell_STORAGE"), "receipt", blob_name)
    blob_client.delete_blob()

    return

@app.cosmos_db_trigger(arg_name="costrig", connection="cosmosdb_config", database_name="ToDoList", container_name="docs")
@app.cosmos_db_output(arg_name="compareDocument", database_name="ToDoList", container_name="docs", connection ="cosmosdb_config", lease_container_name="leases", create_if_not_exists=True)

def fraud(costrig: func.DocumentList, compareDocument: func.Out[func.Document]):
    # Check to see if the document has both an invoice and receipt data
    for doc in costrig:
        if doc.get("invoice") and doc.get("receipt") and not doc.get("comparison"):
            invoice_content = doc.get("invoice").get("content")
            receipt_content = doc.get("receipt").get("content")
            
            # Use Azure Open AI to compare the content of the invoice and receipt
            client = AzureOpenAI(
                api_key = os.getenv("AZURE_OPENAI_API_KEY"),  
                api_version = "2023-05-15",
                azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
                )
            
            response = client.chat.completions.create(
                model="gpt-4", # model = "deployment_name".
                messages=[
                    {"role": "system", "content": '''You are an AI assistant that helps audit invoices and receipts to make sure match. 
                                                If the invoice and receipt do not match, state they do not match. Then explain the reasons why they do not match in bullet point form.
                                                If the invoice and receipt do match, state they match. Then explain the reasons why they do match in bullet point form.'''},
                    {"role": "user", "content": "Invoice: " + invoice_content + "\\n\\nReceipt: " + receipt_content},
                ]
            )

            # Save the comparison results to Cosmos DB  
            doc.data["comparison"] = response.choices[0].message.content
            compareDocument.set(doc)
    return