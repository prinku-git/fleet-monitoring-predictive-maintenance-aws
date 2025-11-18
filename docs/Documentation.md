# ⚙️ IOT FLEET MONITORING AND PREDICTIVE MAINTENANCE DOCUMENTATION

## 1. Project Overview and Architecture

### 1.1. Introduction
This documentation details the implementation of a modern, **event-driven, serverless pipeline** on Amazon Web Services (AWS) for **IoT Fleet Monitoring and Predictive Maintenance**. The system processes real-time vehicle telemetry data, uses Machine Learning for predictive maintenance assessment, and triggers instant alerts for critical safety conditions.

### 1.2. Core Technology Stack & Service Rationale

The solution is architected on the principles of a **Serverless, Event-Driven Architecture**, ensuring the system is highly scalable, cost-effective, and resilient. The strategic selection of AWS services falls into three distinct architectural layers:

#### Data Ingestion and Persistence Layer
This layer handles the storage of both the raw, high-volume telemetry data and the processed, actionable metrics.
* **Amazon S3 (Simple Storage Service):** Utilized as the primary **Data Lake**, providing durable, virtually unlimited, and low-cost storage for the unstructured raw telemetry log files uploaded by the fleet.
* **Amazon DynamoDB:** Serves as the **Real-Time Data Store**. It is a fully managed NoSQL database chosen for its consistent, single-digit millisecond latency, which is essential for storing and querying the processed, structured vehicle data and the ML prediction results at high velocity.

#### Serverless Compute and Machine Learning Layer
This layer contains the core logic for processing data, running predictions, and orchestrating the entire workflow.
* **AWS Lambda:** Acts as the central **Orchestration Layer**. Triggered directly by new file uploads to S3, this serverless compute function executes all business logic: it parses the raw data, invokes the SageMaker endpoint for inference, manages the DynamoDB writes, and evaluates conditions for alerting.
* **Amazon SageMaker:** Provides the **Machine Learning Prediction Endpoint**. The pre-trained model is deployed here as a real-time endpoint, allowing the Lambda function to send vehicle metrics and receive an instant prediction on maintenance requirements (**POSITIVE** or **NEGATIVE**), thereby enabling true predictive maintenance.

#### Security, Monitoring, and Notification Layer
This layer ensures data compliance, operational visibility, and timely communication.
* **AWS KMS (Key Management Service):** Specifically using a **Customer Managed Key (CMK) for SSE-KMS**, it enforces a strong **Data Governance** policy. This ensures that all sensitive data residing in both S3 and DynamoDB is encrypted at rest, meeting critical security and compliance requirements.
* **Amazon SNS (Simple Notification Service):** The core component of the **Instant Alerting** system. When a critical threshold is met (e.g., engine temperature exceeds 100°C), the Lambda function publishes a message to the SNS topic, which instantly fans out the alert as an email notification to the subscribed driver or administrator.
* **Amazon CloudWatch:** Used for **Monitoring and Logging**. It automatically captures all operational logs and metrics from the Lambda function, providing essential diagnostic data necessary for debugging, performance tracking, and maintaining system health.

### 1.3. Architecture Diagram - 

<img width="1366" height="768" alt="Architecture" src="https://github.com/user-attachments/assets/6f11b608-c3d5-4370-8c66-a983b2dd37f4" />


## 2. Foundation Setup: Security (IAM & KMS)

### 2.1. AWS Key Management Service (KMS) Setup
The use of a Customer Managed Key (CMK) is a security best practice for enterprise applications.

**STEP 2.1.1: CREATE A CUSTOMER MANAGED KEY (CMK)**
1.  Navigate to **KMS** service in the AWS Console.
2.  Click **"Customer managed keys"** in the left navigation pane.
3.  Click the **"Create key"** button.
4.  Choose **Symmetric** key type and click **Next**.
5.  Set the alias as `fleet-kms` and add a description.
6.  Define Key Administrators and Key Users (IAM roles/users that can use the key for encryption/decryption). Review and finalize.

<img width="940" height="491" alt="image" src="https://github.com/user-attachments/assets/ebff37c7-78de-4765-959f-18ac18fcd0b4" />
<img width="934" height="525" alt="image" src="https://github.com/user-attachments/assets/a31de7b3-c9a6-4a10-86a5-20bd619bb703" />


### 2.2. IAM Role for Lambda Function
The Lambda function requires permissions to interact with S3, DynamoDB, SNS, SageMaker, and CloudWatch. We adhere to the **Principle of Least Privilege**.

**STEP 2.2.1: Create the Lambda Execution Role**
1.  Navigate to **IAM** service.
2.  Click **"Roles"** and then **"Create role"**.
3.  Select **"AWS service"** as the trusted entity and **"Lambda"** as the use case. Click **Next**.
4.  Create a custom policy named `fleet-lambda-policy` with permissions for:
    * **CloudWatch Logs:** `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents`.
    * **DynamoDB:** `dynamodb:PutItem`, `dynamodb:BatchWriteItem` (limited to `arn:aws:dynamodb:us-east-1:[ACCOUNT_ID]:table/fleet-table`).
    * **S3:** `s3:GetObject` (to read the uploaded file).
    * **SNS:** `sns:Publish` (limited to the fleet SNS Topic ARN).
    * **SageMaker:** `sagemaker:InvokeEndpoint` (limited to the `fleet-alert-ai` endpoint ARN).
    * **KMS:** `kms:Decrypt`, `kms:GenerateDataKey` (limited to the `fleet-kms` ARN).
5.  Attach this policy, name the role `fleet-lambda-role`, and save. 

<img width="836" height="526" alt="image" src="https://github.com/user-attachments/assets/7c8a2e50-63c0-4786-aa20-fbe99121e859" />
<img width="940" height="512" alt="image" src="https://github.com/user-attachments/assets/daee082b-b4f1-4957-8e84-2856e0ccb246" />

---

## 3. Data Layer Setup (S3 AND DYNAMODB)

### 3.1. Amazon S3 Bucket for Ingestion
This bucket receives the raw telemetry files and is secured using the CMK.

**STEP 3.1.1: CREATE THE S3 BUCKET**
1.  Navigate to **S3** service.
2.  Click **"Create bucket"**.
3.  Name the bucket `fleet-iot-data-[YOUR_UNIQUE_ID]`.
4.  Under **"Block Public Access settings"**, ensure **"Block all public access"** is checked (security best practice).
5.  Under **"Default encryption"**, select **"AWS Key Management Service (AWS KMS)"**.
6.  Choose **"Customer managed key (CMK)"** and select the `fleet-kms` key alias.
7.  Click **"Create bucket"**.

<img width="849" height="464" alt="image" src="https://github.com/user-attachments/assets/121791a0-34ea-4e28-93cc-d758556daf82" />
<img width="940" height="513" alt="image" src="https://github.com/user-attachments/assets/990eb612-880b-4f54-9739-d70252e2663e" />


### 3.2. Amazon DynamoDB Table
This table stores the processed, structured data for fast lookup.

**STEP 3.2.1: CREATE THE DYNAMODB TABLE**
1.  Navigate to **DynamoDB** service.
2.  Click **"Create table"**.
3.  Name the table `fleet-table`.
4.  Define the **Primary Key**:
    * **Partition Key:** `device_id` (String)
    * **Sort Key:** `timestamp` (String)
    * *This key structure is crucial for efficient time-series data retrieval per vehicle.*
5.  Under **"Encryption at rest"**, choose **"Customer managed key (CMK)"** and select your `fleet-kms` key.
6.  Click **"Create table"**.

<img width="940" height="513" alt="image" src="https://github.com/user-attachments/assets/686a45bb-f2f1-47d4-80af-8e0322dae046" />
<img width="940" height="488" alt="image" src="https://github.com/user-attachments/assets/3556bda1-b06e-47db-8b91-f254b0cfdcfb" />


---

## 4. ALERTING SETUP (SNS)

### 4.1. CREATE SNS TOPIC
This topic serves as the publication point for critical alerts.

**STEP 4.1.1: CREATE THE SNS TOPIC**
1.  Navigate to **SNS** service.
2.  Click **"Topics"** and then **"Create topic"**.
3.  Choose **"Standard"** type.
4.  Name the topic `fleet-sns`. Click **"Create topic"**.
 
<img width="940" height="488" alt="image" src="https://github.com/user-attachments/assets/4bd7bc9f-194e-4696-a62b-77b0cbb1de07" />
<img width="940" height="490" alt="image" src="https://github.com/user-attachments/assets/a56186a2-9bce-48fa-a032-52575023b0de" />



**STEP 4.1.2: CREATE AN EMAIL SUBSCRIPTION**
1.  On the `fleet-sns` topic details page, click **"Create subscription"**.
2.  Set **Protocol** to **Email**.
3.  Set **Endpoint** to the desired admin/driver email address (e.g., `priyankaraj0919@gmail.com`).
4.  Click **"Create subscription"**.
5.  Check the endpoint email inbox and click the **"Confirm subscription"** link. The status in the SNS Console will change to **"Confirmed"**.
<img width="940" height="490" alt="image" src="https://github.com/user-attachments/assets/274e5539-2eee-4a7b-90ef-a66f8e5a6c77" />
<img width="940" height="490" alt="image" src="https://github.com/user-attachments/assets/df27dbb0-1a14-43c6-a202-200c2ca1bf17" />





---

## 5. COMPUTE & ML LAYER (LAMBDA AND SAGEMAKER)

### 5.1. SAGEMAKER MODEL DEPLOYMENT
A model trained for binary classification (maintenance required/not required) must be deployed to a real-time endpoint.

**STEP 5.1.1: DEPLOY THE MODEL ENDPOINT**
* **Action:** Ensure your trained SageMaker model is deployed as a real-time endpoint.
* **Configuration:** The endpoint name must be set to `fleet-alert-ai` so the Lambda function can correctly invoke it.
* **Note:** The Lambda function will send vehicle sensor data to this endpoint and receive a prediction label (e.g., **POSITIVE** or **NEGATIVE**).

<img width="940" height="490" alt="image" src="https://github.com/user-attachments/assets/d0e98d63-7610-4d27-80f7-035e2444dcba" />


### 5.2. AWS LAMBDA FUNCTION CREATION

**STEP 5.2.1: CREATE THE FUNCTION**
1.  Navigate to **Lambda** service.
2.  Click **"Create function"**.
3.  Select **"Author from scratch"**.
4.  Set **Function name** to `fleet-lambda`.
5.  Set **Runtime** to a Python version (e.g., **Python 3.10**).
6.  Under **"Change default execution role"**, select **"Use an existing role"** and choose `fleet-lambda-role`.
7.  Click **"Create function"**.

<img width="940" height="490" alt="image" src="https://github.com/user-attachments/assets/11c2aef9-7e52-4c57-b43c-e0f6b8bc6f42" />


**STEP 5.2.2: ADD S3 TRIGGER**
1.  In the Lambda function designer, click **"Add trigger"**.
2.  Select **"S3"** from the list of sources.
3.  Choose the S3 bucket `fleet-iot-data-[YOUR_UNIQUE_ID]`.
4.  Set **Event type** to **"All object create events"**.
5.  Acknowledge the recursive invocation warning and click **"Add"**.

<img width="940" height="490" alt="image" src="https://github.com/user-attachments/assets/612ab6ab-5c55-41d1-b6f9-0c3731ee30d4" />
<img width="940" height="490" alt="image" src="https://github.com/user-attachments/assets/2ae686f0-3248-4ab5-bf05-a0c0f956de71" />



---

## 6. Lambda Function Code and Logic

### 6.1. Code Integration

**STEP 6.1.1: PASTE THE PYTHON CODE**
In the Lambda Console, paste your Python logic into the `lambda_function.py` editor.

<img width="940" height="490" alt="image" src="https://github.com/user-attachments/assets/f8218daf-33b5-4aab-bdaa-78ba8fcb9e24" />


**KEY CODE LOGIC:**

| Code Section | Purpose | Detail |
| :--- | :--- | :--- |
| `Boto3 Clients` | Initialization | Sets up clients for **S3, DynamoDB, SNS, and SageMaker Runtime** using the `fleet-lambda-role`'s permissions. |
| `convert_floats_to_decimal` | Data Type Handling | A crucial utility function that recursively converts all Python float values in the JSON payload into **DynamoDB's native Decimal** type before writing. |
| `S3 Read` | Data Ingestion | Reads the raw log file triggered by the event from the S3 bucket. |
| `Data Parsing` | Transformation | Extracts key fields (`device_id`, `timestamp`, `engine_temp_c`) from the raw log line and converts them to a structured dictionary/JSON. |
| `SageMaker Invocation` | Prediction | Calls the `fleet-alert-ai` endpoint with the structured data and retrieves the `prediction_label` (e.g., **POSITIVE**). |
| `DynamoDB Write` | Storage | Writes the complete, structured payload (including the prediction) to the `fleet-table` using the `PutItem` operation. |
| `SNS Alert Condition` | Alerting | An `if` condition checks the `engine_temp_c` value. If it exceeds a predefined threshold (e.g., **100.0°C**), it calls `sns_client.publish()` to the `fleet-sns` topic. |

---

## 7. TESTING AND VERIFICATION

**STEP 7.1.1: Prepare Test Data**
Create a simple text file (`test-data.txt`) simulating vehicle logs. Include at least one record where the temperature is **above 100°C** to trigger the SNS alert.

```text
device_id:VHC001, timestamp:2025-11-15T10:00:00Z, engine_temp_c:124.0
device_id:VHC002, timestamp:2025-11-15T10:01:00Z, engine_temp_c:95.5

![Uploading image.png…]()

STEP 7.1.2: TRIGGER THE WORKFLOW

Action: Upload the test-data.txt file to the fleet-iot-data S3 bucket.

Process: The S3 upload event immediately triggers the fleet-lambda function.

[Insert S3 Upload Confirmation Screenshot Here]

STEP 7.1.3: VERIFICATION OF SNS ALERT

Expected Outcome: An alert email should be received for VHC001 (124.0°C).

Purpose: Confirms that the SNS critical alert mechanism is working correctly.

[Insert Received SNS Alert Email Screenshot Here]

STEP 7.1.4: VERIFICATION OF DYNAMODB STORAGE

Expected Outcome: Two new items should be visible in the fleet-table:

VHC001

VHC002

Validation: Each entry must contain the SageMaker prediction label (e.g., POSITIVE).

[Insert DynamoDB Table Content Screenshot Here]

STEP 7.1.5: VERIFICATION OF LOGS

Expected Outcome: The CloudWatch Log Group for fleet-lambda should show:

Successful DynamoDB write

Successful SNS publish action

Overall Lambda execution logs

[Insert CloudWatch Log Events Screenshot Here]

8. Project Summary and Conclusion

This project establishes a complete IoT Fleet Monitoring and Predictive Maintenance solution using AWS Serverless Services.

System Achievement Highlights
1. End-to-End Automation

Automated data ingestion

Real-time processing

ML prediction

Instant alerting

2. Predictive Intelligence

SageMaker predicts maintenance needs, reducing downtime and improving safety.

3. Best-Practice Security

IAM with Least Privilege

AWS KMS (SSE-KMS) encryption for S3 and DynamoDB

4. Scalability and Cost Efficiency

Serverless architecture auto-scales and reduces operational overhead.

Conclusion

This project demonstrates strong knowledge in cloud architecture, security, automation, and machine learning integration on AWS.

