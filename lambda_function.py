import boto3
import json
import re
from decimal import Decimal

s3_client = boto3.client('s3', region_name='your-region')
dynamodb = boto3.resource('dynamodb', region_name='your-region')
sns_client = boto3.client('sns', region_name='your-region')
cloudwatch = boto3.client('cloudwatch', region_name='your-region')
sagemaker_runtime = boto3.client('sagemaker-runtime', region_name='your-region')

DYNAMO_TABLE_NAME = 'your-dynamodb-table'
SAGEMAKER_ENDPOINT = 'your-sagemaker-endpoint'
FLEET_BUCKET = 'your-bucket-name'
FLEET_FILE = 'your-file-name'

VEHICLE_TO_SNS = {
    'VHC001': 'arn:aws:sns:your-region:your-account-id:your-topic-name',
    'VHC002': 'arn:aws:sns:your-region:your-account-id:your-other-topic'
}

table = dynamodb.Table(DYNAMO_TABLE_NAME)

def convert_floats_to_decimal(obj):
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: convert_floats_to_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_floats_to_decimal(i) for i in obj]
    else:
        return obj

def send_cloudwatch_metric(device_id, engine_temp):
    if engine_temp == 0:
        return
    cloudwatch.put_metric_data(
        Namespace='FleetMonitoring',
        MetricData=[{
            'MetricName': 'EngineTemperature',
            'Dimensions': [{'Name': 'VehicleID', 'Value': device_id}],
            'Value': float(engine_temp),
            'Unit': 'None'
        }]
    )

def send_sns_alert(device_id, timestamp, speed, fuel, engine_temp):
    topic_arn = VEHICLE_TO_SNS.get(device_id)
    if not topic_arn:
        return

    message = f"""⚠️ Fleet Vehicle Alert !

Vehicle ID: {device_id}
Timestamp: {timestamp}
Speed: {speed} km/h
Fuel Level: {fuel}%
Engine Temperature: {engine_temp}°C

Engine temperature is above safe threshold. Immediate inspection recommended.

This is an automated alert from the Fleet Monitoring System.
"""
    sns_client.publish(
        TopicArn=topic_arn,
        Message=message,
        Subject=f'Fleet Vehicle Alert: {device_id}'
    )

def invoke_sagemaker(sentence):
    try:
        response = sagemaker_runtime.invoke_endpoint(
            EndpointName=SAGEMAKER_ENDPOINT,
            ContentType='application/x-text',
            Accept='application/json',
            Body=sentence.encode('utf-8')
        )
        result = json.loads(response['Body'].read().decode('utf-8'))

        if 'probabilities' in result:
            probs_raw = result['probabilities']
            if isinstance(probs_raw, dict) and 'L' in probs_raw:
                prob_list = probs_raw['L']
                probs = [float(x['N']) for x in prob_list]
            else:
                probs = [float(x) for x in probs_raw]
        else:
            probs = [0.0, 0.0]

        max_index = probs.index(max(probs))
        LABELS = ["POSITIVE", "NEGATIVE"]
        label = LABELS[max_index]
        score = probs[max_index]

        return {"label": label, "score": score}

    except Exception:
        return {"label": "UNKNOWN", "score": 0.0}

def lambda_handler(event, context):
    records = event.get('Records', [])
    if not records:
        records = [{'s3': {'bucket': {'name': FLEET_BUCKET}, 'object': {'key': FLEET_FILE}}}]

    for record in records:
        bucket_name = record['s3']['bucket']['name']
        object_key = record['s3']['object']['key']

        if bucket_name != FLEET_BUCKET or object_key != FLEET_FILE:
            continue

        s3_response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
        content = s3_response['Body'].read().decode('utf-8')
        sentences = content.strip().split('\n')

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            device_match = re.search(r'device_id (\S+)', sentence)
            timestamp_match = re.search(r'timestamp ([\d-]+ [\d:]+)', sentence)
            speed_match = re.search(r'speed_kmph (\d+\.?\d*)', sentence)
            fuel_match = re.search(r'fuel_level_percent (\d+\.?\d*)', sentence)
            engine_match = re.search(r'engine_temp_c (\d+\.?\d*)', sentence)

            device_id = device_match.group(1) if device_match else 'UNKNOWN'
            timestamp = timestamp_match.group(1) if timestamp_match else ''
            speed = float(speed_match.group(1)) if speed_match else 0.0
            fuel = float(fuel_match.group(1)) if fuel_match else 0.0
            engine_temp = float(engine_match.group(1)) if engine_match else 0.0

            send_cloudwatch_metric(device_id, engine_temp)
            prediction = invoke_sagemaker(sentence)

            if engine_temp > 100:
                send_sns_alert(device_id, timestamp, speed, fuel, engine_temp)

            item = {
                'device_id': device_id,
                'timestamp': timestamp,
                'sentence': sentence,
                'speed_kmph': speed,
                'fuel_level_percent': fuel,
                'engine_temp_c': engine_temp,
                'prediction': prediction
            }

            if timestamp:
                table.put_item(Item=convert_floats_to_decimal(item))

    return {
        'statusCode': 200,
        'body': json.dumps('Fleet sentences processed successfully')
    }
