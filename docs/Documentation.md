# ⚙️ IOT FLEET MONITORING AND PREDICTIVE MAINTENANCE WITH SAGEMAKER - DOCUMENTATION

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
5.  Set the alias name and add a description.
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
    * **DynamoDB:** `dynamodb:PutItem`, `dynamodb:BatchWriteItem` (limited to `arn:aws:dynamodb:us-east-1:[ACCOUNT_ID]:table/DYANAMODB-NAME`).
    * **S3:** `s3:GetObject` (to read the uploaded file).
    * **SNS:** `sns:Publish` (limited to the fleet SNS Topic ARN).
    * **SageMaker:** `sagemaker:InvokeEndpoint` (limited to the `ENDPOINT-NAME` endpoint ARN).
    * **KMS:** `kms:Decrypt`, `kms:GenerateDataKey` (limited to the `KMS-NAME` ARN).
5.  Attach this policy, name the role `LAMBDA-NAME`, and save. 

<img width="836" height="526" alt="image" src="https://github.com/user-attachments/assets/7c8a2e50-63c0-4786-aa20-fbe99121e859" />
<img width="940" height="512" alt="image" src="https://github.com/user-attachments/assets/daee082b-b4f1-4957-8e84-2856e0ccb246" />

---

## 3. Data Layer Setup (S3 AND DYNAMODB)

### 3.1. Amazon S3 Bucket for Ingestion
This bucket receives the raw telemetry files and is secured using the CMK.

**STEP 3.1.1: CREATE THE S3 BUCKET**
1.  Navigate to **S3** service.
2.  Click **"Create bucket"**.
3.  Name the bucket .
4.  Under **"Block Public Access settings"**, ensure **"Block all public access"** is checked (security best practice).
5.  Under **"Default encryption"**, select **"AWS Key Management Service (AWS KMS)"**.
6.  Choose **"Customer managed key (CMK)"** and select the `KMS-NAME` key alias.
7.  Click **"Create bucket"**.

<img width="849" height="464" alt="image" src="https://github.com/user-attachments/assets/121791a0-34ea-4e28-93cc-d758556daf82" />
<img width="940" height="513" alt="image" src="https://github.com/user-attachments/assets/990eb612-880b-4f54-9739-d70252e2663e" />


### 3.2. Amazon DynamoDB Table
This table stores the processed, structured data for fast lookup.

**STEP 3.2.1: CREATE THE DYNAMODB TABLE**
1.  Navigate to **DynamoDB** service.
2.  Click **"Create table"**.
3.  Name the table .
4.  Define the **Primary Key**:
    * **Partition Key:** `device_id` (String)
    * **Sort Key:** `timestamp` (String)
    * *This key structure is crucial for efficient time-series data retrieval per vehicle.*
5.  Under **"Encryption at rest"**, choose **"Customer managed key (CMK)"** and select your `KMS-NAME`` key.
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
4.  Name the topic. Click **"Create topic"**.
 
<img width="940" height="488" alt="image" src="https://github.com/user-attachments/assets/4bd7bc9f-194e-4696-a62b-77b0cbb1de07" />



**STEP 4.1.2: CREATE AN EMAIL SUBSCRIPTION**
1.  On the topic details page, click **"Create subscription"**.
2.  Set **Protocol** to **Email**.
3.  Set **Endpoint** to the desired admin/driver email address (e.g., `ABCD@gmail.com`).
4.  Click **"Create subscription"**.
5.  Check the endpoint email inbox and click the **"Confirm subscription"** link. The status in the SNS Console will change to **"Confirmed"**.
<img width="940" height="490" alt="image" src="https://github.com/user-attachments/assets/274e5539-2eee-4a7b-90ef-a66f8e5a6c77" />

---

## 5. COMPUTE & ML LAYER (LAMBDA AND SAGEMAKER)

### 5.1. SAGEMAKER MODEL DEPLOYMENT
A model trained for binary classification (maintenance required/not required) must be deployed to a real-time endpoint.

**STEP 5.1.1: DEPLOY THE MODEL ENDPOINT**
* **Action:** Ensure your trained SageMaker model is deployed as a real-time endpoint.
* **Configuration:** The endpoint name must be set to `ENDPOINT-NAME` so the Lambda function can correctly invoke it.
* **Note:** The Lambda function will send vehicle sensor data to this endpoint and receive a prediction label (e.g., **POSITIVE** or **NEGATIVE**).

<img width="1366" height="768" alt="23" src="https://github.com/user-attachments/assets/0cfebf0f-d9ff-4c63-bf66-58bc72b259d8" />


### 5.2. AWS LAMBDA FUNCTION CREATION

**STEP 5.2.1: CREATE THE FUNCTION**
1.  Navigate to **Lambda** service.
2.  Click **"Create function"**.
3.  Select **"Author from scratch"**.
4.  Set **Function name** .
5.  Set **Runtime** to a Python version (e.g., **Python 3.10**).
6.  Under **"Change default execution role"**, select **"Use an existing role"** and choose `LAMBDA-NAME`.
7.  Click **"Create function"**.

<img width="1366" height="711" alt="12" src="https://github.com/user-attachments/assets/e73bcd5f-274e-47a3-843d-863a954d1b6d" />


**STEP 5.2.2: ADD S3 TRIGGER**
1.  In the Lambda function designer, click **"Add trigger"**.
2.  Select **"S3"** from the list of sources.
3.  Choose the S3 bucket `BUCKET-NAME`.
4.  Set **Event type** to **"All object create events"**.
5.  Acknowledge the recursive invocation warning and click **"Add"**.

<img width="1366" height="709" alt="14" src="https://github.com/user-attachments/assets/bbfdb01b-8338-474c-a113-76f8da0e9f1d" />
<img width="1366" height="709" alt="15" src="https://github.com/user-attachments/assets/09a5bf2a-14e2-463b-9dcb-9639aeed3537" />

---

## 6. Lambda Function Code and Logic

### 6.1. Code Integration

**STEP 6.1.1: PASTE THE PYTHON CODE**
In the Lambda Console, paste your Python logic into the `lambda_function.py` editor.

For FULL CODE : https://github.com/prinku-git/fleet-monitoring-predictive-maintenance-aws/blob/main/lambda_function.py

<img width="1366" height="709" alt="16" src="https://github.com/user-attachments/assets/bc225535-5176-4618-81c8-0febc9eb5b4b" />



**KEY CODE LOGIC:**

| Code Section | Purpose | Detail |
| :--- | :--- | :--- |
| `Boto3 Clients` | Initialization | Sets up clients for **S3, DynamoDB, SNS, and SageMaker Runtime** using the `LAMBDA-NAME`'s permissions. |
| `convert_floats_to_decimal` | Data Type Handling | A crucial utility function that recursively converts all Python float values in the JSON payload into **DynamoDB's native Decimal** type before writing. |
| `S3 Read` | Data Ingestion | Reads the raw log file triggered by the event from the S3 bucket. |
| `Data Parsing` | Transformation | Extracts key fields (`device_id`, `timestamp`, `engine_temp_c`) from the raw log line and converts them to a structured dictionary/JSON. |
| `SageMaker Invocation` | Prediction | Calls the `ENDPOINT-NAME` endpoint with the structured data and retrieves the `prediction_label` (e.g., **POSITIVE**). |
| `DynamoDB Write` | Storage | Writes the complete, structured payload (including the prediction) to the `DYNAMODB-NAME` using the `PutItem` operation. |
| `SNS Alert Condition` | Alerting | An `if` condition checks the `engine_temp_c` value. If it exceeds a predefined threshold (e.g., **100.0°C**), it calls `sns_client.publish()` to the `SNS-TOPIC-NAME` topic. |

---
### STEP 7.1.2: TRIGGER THE WORKFLOW
Upload the **`test-data.txt`** file to the **`S3-BUCKET-NAME`** S3 bucket.  
The S3 upload event immediately triggers the **`LAMBDA-NAME`** function.

<img width="1366" height="711" alt="25" src="https://github.com/user-attachments/assets/8c68f5d2-238d-4ab9-9614-608067528dfa" />

---

### STEP 7.1.3: VERIFICATION OF SNS ALERT
Check the email inbox subscribed to the **`SNS-TOPIC-NAME`** topic.

**Expected Outcome:**  
An alert email should be received for **VHC001 (124.0°C)**, confirming the critical-condition alert mechanism is functional.

<img width="1366" height="702" alt="26" src="https://github.com/user-attachments/assets/bbcd8aec-2205-4645-b4fa-fc14b649309c" />


---

### STEP 7.1.4: VERIFICATION OF DYNAMODB STORAGE
Navigate to the **`DYNAMODB-NAME`** in DynamoDB.

**Expected Outcome:**  
Two new items should be visible:

- **VHC001**  
- **VHC002**

Both records should include the SageMaker prediction label (e.g., **POSITIVE**).

<img width="1366" height="709" alt="27" src="https://github.com/user-attachments/assets/6cb8a4b8-e73c-4123-875e-99d9b6d4e059" />


---

### STEP 7.1.5: VERIFICATION OF LOGS
Navigate to the CloudWatch Log Group for the **`LAMBDA-FUNCTION`** function.

**Expected Outcome:**  
Logs should show:

- Successful execution  
- DynamoDB write  
- SNS publish  
- SageMaker prediction result  

<img width="1366" height="715" alt="28" src="https://github.com/user-attachments/assets/de9b89a2-0005-4f29-a7bc-326de17852e3" />


---

## 8. Project Summary and Conclusion
This project successfully establishes a **robust, scalable, and secure IoT Fleet Monitoring and Predictive Maintenance solution** entirely built on **AWS Serverless Architecture**.

---

### System Achievement Highlights

#### **End-to-End Automation**
A fully automated workflow handling ingestion → processing → prediction → alerting.

#### **Real-Time Capability**
Event-driven pipeline using S3 + Lambda ensures real-time detection and alerts.

#### **Predictive Intelligence**
SageMaker model provides proactive maintenance intelligence.

#### **Best-Practice Security**
IAM least privilege + SSE-KMS encryption with CMK ensures enterprise security.

#### **Scalability & Cost Efficiency**
Serverless (Lambda, DynamoDB, SNS, S3) ensures auto-scaling and low cost.

---

### Conclusion
This project demonstrates strong cloud architecture, security design, serverless expertise, and ML integration—delivering a scalable, cost-efficient solution suitable for enterprise deployment.











