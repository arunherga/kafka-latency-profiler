def read_ccloud_config(config_file,use):
    conf = {}
    with open(config_file) as fh:
        for line in fh:
            line = line.strip()
            if len(line) != 0 and line[0] != "#":
                parameter, value = line.strip().split('=', 1)
                conf[parameter] = value.strip()
    return config_sorter(conf,use)

def config_sorter(conf,use):
    if (use == 'producer'):
        req = ['bootstrap.servers','security.protocol','sasl.mechanisms','sasl.username','sasl.password']
        props = {key: conf[key] for key in req}
        return props
    elif (use == 'sr'):
        req =['url','basic.auth.user.info']
        props = {key:conf[key] for key in req}
        return props
    elif (use == 'consumer'):
        req = ['bootstrap.servers','group.id','security.protocol','sasl.mechanisms','sasl.username','sasl.password','auto.offset.reset','enable.auto.commit','connections.max.idle.ms']
        props = {key:conf[key] for key in req}
        return props

def write_to_csv(file_location, data):          
    data.to_csv(f'{file_location}', index=False)
    print(f"\nData written to {file_location} successfully.")
# class User(object):
#     """
#     User record
#     """

#     def __init__(self, ordertime=None, orderid=None, itemid=None, orderunits=None, address=None):
#         self.ordertime = ordertime
#         self.orderid = orderid
#         self.itemid = itemid
#         self.orderunits = orderunits
#         self.address = address



# def dict_to_user(obj, ctx):
#     """
#     Converts object literal(dict) to a Order instance.
#     """

#     if obj is None:
#         return None

#     return User(ordertime=obj['ordertime'],
#              orderid=obj['orderid'],
#              itemid=obj['itemid'],
#              orderunits=obj['orderunits'],
#              address=obj['address'])

import argparse
import time
from datetime import datetime
from confluent_kafka import Consumer, TopicPartition, KafkaError,DeserializingConsumer,Producer
from confluent_kafka.schema_registry.json_schema import JSONDeserializer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.serialization import SerializationContext, MessageField,StringDeserializer
from confluent_kafka.schema_registry.avro import AvroSerializer,AvroDeserializer
import random
import json
import csv
import numpy as np
import pandas as pd
import argparse
import re

if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='Kafka Consumer')

    parser.add_argument('--consumer_config_file', required=True,help='Absolute path to configuration.properties file that contains settings and properties used to configure a Kafka consumer application to consume messages from a Kafka cluster.')
    parser.add_argument('--bootstrap_servers', required=False, help='A list of host/port pairs to use for establishing the initial connection to the Kafka cluster. list should be in the form host1:port1,host2:port2,...')
    parser.add_argument('--input_topic', required=False, help='Kafka topic to consume messages from.')
    parser.add_argument('--group_id', default="newgroup01", help='A unique string that identifies the consumer group this consumer belongs to. This property is required if the consumer uses either the group management functionality by using subscribe(topic) or the Kafka-based offset management strategy')
    #parser.add_argument('--key-deserializer',help='Deserializer class for key that implements the org.apache.kafka.common.serialization.Deserializer interface.')
    #parser.add_argument('--value-deserializer',help='Deserializer class for value that implements the org.apache.kafka.common.serialization.Deserializer interface.')
    #parser.add_argument('--fetch-min-bytes',help='The minimum amount of data the server should return for a fetch request. If insufficient data is available the request will wait for that much data to accumulate before answering the request. The default setting is 1 byte')
    #parser.add_argument('--heartbeat-interval-ms',help='The expected time between heartbeats to the consumer coordinator when using Kafkas group management facilities. Heartbeats are used to ensure that the consumers session stays active and to facilitate rebalancing when new consumers join or leave the group. The default setting is 3 seconds')
    #parser.add_argument('--enable-auto-commit',type=bool,choices={True,False},help='It determines whether the Kafka consumer should automatically commit its current offset position to the Kafka broker at regular intervals. When enabled to True (which is by default) the consumer will automatically commit the offset based on the "auto.commit.interval.ms" property value. If "enable.auto.commit" is set to "false", the consumer must manually commit the offset position after processing messages.  ')
    #parser.add_argument('--auto-offset-reset',choices={'earliest','latest'},help='It determines what to do when there is no initial offset or when the current offset is out of range.earliest: automatically reset the offset to the earliest offset.latest: automatically reset the offset to the latest offset.')
    parser.add_argument('--enable_sampling',action="store_true",default=False,help='enable/disable sampling by 30 percent')
    parser.add_argument('--run_interval',default=20,type=int,help='duration of time during which the consumer is actively running and consuming messages from a Kafka topic.')
    parser.add_argument('--t1',default='IngestionTime',help='It is one of time parameter(used to measure latency->t2-t1). value.<column name> - this is pointer to message value timestamp i.e any column/object in value that points to event time. key.<column name> - this is pointer to message key timestamp i.e any column/object in key that points to event time. IngestionTime imply time when message is recorded in kafka topic.')
    parser.add_argument('--t2',default='consumerWallClockTime',choices={'consumerWallClockTime','IngestionTime'},help='It is one of the time parameter (used to measure latency->t2-t1). ConsumerWallClockTime -this is a pointer to the current time, as seen in the conusumer. IngestionTime imply time when message is recorded in kafka topic')
    parser.add_argument('--consumer_output',default='console',choices={'console','localFileDump','dumpToTopic'},help='console - Consumer output is printed in console. localFileDump - stores the output of consumer as a csv file(by default) and require to be followed by --result-dump-local-filepath. dumpToTopic - stores consumer output in kafka topic requires to be followed by --result-dump-producer-config')
    parser.add_argument('--result_dump_local_filepath',help='file path to store consumer output ')
    #parser.add_argument('--result_dump_producer_config',help=' configuration.properties file that contains settings and properties used to configure a Kafka producer application to dump consumer results' )
    parser.add_argument('--output_topic',help='Kafka topic to dump consumer output')
    #parser.add_argument('--consumer_schema_json',default='None',help='File path of consumer JsonSchema')
    #parser.add_argument('--confluent_sr_config',default='None',help='Enter url of conflunt schema registary')
    parser.add_argument('--value_deserializer',required=True,choices={'AvroDeserializer','JSONSchemaDeserializer','StringDeserializer','JSONDeserializer'},help='Deserializer class for value that implements the org.apache.kafka.common.serialization.Deserializer interface.')
    parser.add_argument('--key-deserializer',choices={'AvroDeserializer','JSONSchemaDeserializer','StringDeserializer','JSONDeserializer'},help='Deserializer class for key that implements the org.apache.kafka.common.serialization.Deserializer interface.')
    parser.add_argument('--producer_config_file',help='configuration.properties file that contains properties used to configure producer')



    args = parser.parse_args()

    consumer_properties = read_ccloud_config(args.consumer_config_file,'consumer')
    topic=args.input_topic
    consumer_properties['group.id']=args.group_id
    sampling = (args.enable_sampling == True)
    run_interval=args.run_interval
    t1=args.t1
    t2=args.t2
    output_type=args.consumer_output
    local_filepath=args.result_dump_local_filepath
    #producer_prop=args.result_dump_producer_config
    output_topic=args.output_topic
    #schema_location=args.consumer_schema_json
    #confluent_sr_config=args.confluent_sr_config
    value_deserializer = args.value_deserializer
    key_deserializer = args.key_deserializer
    producer_properties = read_ccloud_config(args.producer_config_file,'producer')
    

    if t1 != 'IngestionTime':
      
      ordertime_key = t1.split('.')[1]

      pattern = r'"{}":(\d+)'.format(ordertime_key)

    print("\n\n\t\t\t\t\t\t\t\t\t\t\tConsumer has started!!\n")
    
    
    # if (schema_location != 'None'):
    
    #   with open("schema.json") as f:
    
    #       schema_str = f.read()
    


    # if (key_deserializer == ('AvroDeserializer' or 'JSONSchemaDeserializer')):
    
    #     schema_registary =SchemaRegistryClient(read_ccloud_config(args.config_file,'sr'))
   
    #     latest = schema_registary.get_latest_version(f'{topic}-key')
        
    #     schema_str_key = schema_registary.get_schema(latest.schema_id)
   
    #     schema_str_key=schema_str_key.schema_str
    #      #print(schema_str)


    # if key_deserializer == 'JSONSchemaDeserializer':         

    #   #json_deserializer = JSONDeserializer(schema_str,from_dict=dict_to_user)
    #   json_deserializer = JSONDeserializer(schema_str=schema_str_key)
    
    
    # elif key_deserializer == 'AvroDeserializer':
    
    #   schema_registry_client = SchemaRegistryClient(read_ccloud_config(args.config_file,'sr'))
    
    #   avro_deserializer = AvroDeserializer(schema_registry_client=schema_registry_client,schema_str=schema_str_key)
    
    
    # elif key_deserializer == 'StringDeserializer':
    
    #    string_deserializer = StringDeserializer(codec='utf_8')

    t = False

    if (value_deserializer == ('AvroDeserializer') or value_deserializer == ('JSONSchemaDeserializer')):
    
        schema_registary =SchemaRegistryClient(read_ccloud_config(args.consumer_config_file,'sr'))
   
        latest = schema_registary.get_latest_version(f'{topic}-value')
        
        schema_str = schema_registary.get_schema(latest.schema_id)
   
        schema_str=schema_str.schema_str
         #print(schema_str)
        t = True


    if value_deserializer == 'JSONSchemaDeserializer':         

      #json_deserializer = JSONDeserializer(schema_str,from_dict=dict_to_user)
      json_deserializer = JSONDeserializer(schema_str=schema_str)

      
    
    
    elif value_deserializer == 'AvroDeserializer':
    
      schema_registry_client = SchemaRegistryClient(read_ccloud_config(args.consumer_config_file,'sr'))
    
      avro_deserializer = AvroDeserializer(schema_registry_client=schema_registry_client,schema_str=schema_str)

      
    
    
    elif value_deserializer == 'StringDeserializer':
    
       string_deserializer = StringDeserializer(codec='utf_8')

    consumer=Consumer(consumer_properties)    
    
    consumer.subscribe([topic])
    
    topic_partitions = [TopicPartition(topic, p) for p in consumer.list_topics(topic).topics[topic].partitions]
    
    #print(topic_partitions)
    print("Number of partition in the topic:",len(topic_partitions))

    # total_message = 0
    
    
    # for tp in topic_partitions:
    
    #     total_message=total_message+consumer.get_watermark_offsets(tp)[1]
    
    # print("\nTotal Messages in topic\t:\t", total_message)
    
    count = 0
    
    avg = 0
    
    latency_arry = []
    
    start_time=time.time()
    
    elapsed_time=0    

    #print(t)
    

    try:

        while elapsed_time<run_interval:
          
            msg = consumer.poll(1.0)
          
            elapsed_time = time.time()-start_time
            #print(elapsed_time)
          
            if msg is None:
          
                # print(f"Consumer will close in {int(run_interval-elapsed_time)}seconds")
                #print("waiting")
                continue
          
          
            if msg.error():
          
          
                if msg.error().code() == KafkaError._PARTITION_EOF:
          
                    print(f'Reached end of partition {msg.topic()}-{msg.partition()}')

                else:
          
                    print(f'Error while consuming from partition {msg.topic()}-{msg.partition()}: {msg.error()}')
          
            else:
          
          
                #mm = msg.value().decode("utf-8")
                #print(f'Consumed message from partition {msg.topic()}-{msg.partition()}, offset {msg.offset()}: {msg.value().decode("utf-8")}')
                #print(mm)
                #print("i am here")

                if t:

                  #print(t)
          
          
                  if value_deserializer == 'JSONSchemaDeserializer':
            
                    user = json_deserializer(msg.value(), SerializationContext(msg.topic(), MessageField.VALUE))

                    #print(t)
            
                  elif value_deserializer == 'AvroDeserializer':
            
                    user = avro_deserializer(msg.value(), SerializationContext(msg.topic(), MessageField.VALUE))
                  # if deserializer == 'StringDeserializer':
                  #     user = string_deserializer(msg.value(), SerializationContext(msg.topic(), MessageField.VALUE))
                    #t = False


                  
            
                  #if ((user is not None) and (value_deserializer == ('JSONSchemaDeserializer' or 'AvroDeserializer'))) :
                  if user is not None:
                      
                      count=count+1
                      
                      # print("Order record {}: \n \tordertime: {}\n"
                      #     "\tItem Number: {}\n"
                      #     "\tAddress: {}\n"
                      #     .format(msg.key(), user.ordertime,
                      #             user.itemid,
                      #             user.address))
                      #print(user)
                
                      #print(user['ordertime']) 
                      if t1=="IngestionTime":
                          time1=int(msg.timestamp()[1])
                          
                  
                      elif (t1.split('.')[0]) =='value':
                          #i = t1.split('.')[1]
                          time1 = user[t1.split('.')[1]]
                  
                  
                      # elif (t1.split('.')[0]) == 'key':
                  
                      #     #i = t1.split('.')[1]
                      #     #time1 = getattr(user,i)
                      #     user1 = json_deserializer(msg.key(), SerializationContext(msg.topic(), MessageField.VALUE))
                      #     time1 = user1[t1.split('.')[1]]               

                      
                      if t2 == 'IngestionTime':
                  
                          time2=int(msg.timestamp()[1])
                  
                  
                      elif t2 == 'consumerWallClockTime':
                  
                          time2= time.time()*1000               
                      
                      latency = (time2-time1)
                      latency_arry.append(latency)
                
                if value_deserializer == 'JSONDeserializer':
                    
                    if msg is not None:
                        
                        count = count+1
                        val = msg.value().decode('utf-8')
                        #print(val)
                        # ordertime_key = "ordertime"
                        # pattern = r'"{}":(\d+)'.format(ordertime_key)
                        
                        
                        mat = re.search(pattern,val)
                        #print(mat.group(1))
                        
                        if t1=="IngestionTime":
                          time1=int(msg.timestamp()[1])
                        elif (t1.split('.')[0]) =='value':
                            time1 = int(mat.group(1))
                        
                        if t2 == 'IngestionTime':
                  
                          time2=int(msg.timestamp()[1])
                  
                  
                        elif t2 == 'consumerWallClockTime':
                  
                          time2= time.time()*1000               
                      
                        latency = (time2-time1)
                        latency_arry.append(latency)


                
                
                # if ((user is not None) and (value_deserializer == ('StringDeserializer' or 'JSONDeserializer'))):
                    
                #     count = count+1

                #     val = msg.value().decode('utf-8')

                #     if t1=="IngestionTime":
                #         time1=int(msg.timestamp()[1])
                    
                #     else:
                #         mat = re.search(pattern,val)
                #         time1 = int(mat.group(1))

                    
                #     if t2 == 'IngestionTime':
                
                #         time2=int(msg.timestamp()[1])
                
                
                #     elif t2 == 'consumerWallClockTime':
                
                #         time2= time.time()*1000               
                    
                #     latency = (time2-time1)
                    
                #     latency_arry.append(latency)
                

                # if key_deserializer == 'JSONSchemaDeserializer':
          
                #   user = json_deserializer(msg.key(), SerializationContext(msg.topic(), MessageField.KEY))
          
          
                # elif key_deserializer == 'AvroDeserializer':
          
                #   user = avro_deserializer(msg.key(), SerializationContext(msg.topic(), MessageField.KEY))
                # # if deserializer == 'StringDeserializer':
                # #     user = string_deserializer(msg.value(), SerializationContext(msg.topic(), MessageField.VALUE))
                
          
                # if ((user is not None) and (key_deserializer == ('JSONSchemaDeserializer' or 'AvroDeserializer'))) :
                
                #     count=count+1
                    
                #     # print("Order record {}: \n \tordertime: {}\n"
                #     #     "\tItem Number: {}\n"
                #     #     "\tAddress: {}\n"
                #     #     .format(msg.key(), user.ordertime,
                #     #             user.itemid,
                #     #             user.address))
                #     #print(user)
              
                #     #print(user['ordertime']) 
                #     if t1=="IngestionTime":
                #         time1=int(msg.timestamp()[1])
                        
                
                #     elif (t1.split('.')[0]) =='value':
                #         #i = t1.split('.')[1]
                #         time1 = user[t1.split('.')[1]]
                
                
                #     elif (t1.split('.')[0]) == 'key':
                
                #         #i = t1.split('.')[1]
                #         #time1 = getattr(user,i)
                #         user1 = json_deserializer(msg.key(), SerializationContext(msg.topic(), MessageField.VALUE))
                #         time1 = user1[t1.split('.')[1]]               

                    
                #     if t2 == 'IngestionTime':
                
                #         time2=int(msg.timestamp()[1])
                
                
                #     elif t2 == 'consumerWallClockTime':
                
                #         time2= time.time()*1000               
                    
                #     latency = (time2-time1)
                #     latency_arry.append(latency)
                
                
                # if ((user is not None) and (key_deserializer == ('StringDeserializer' or 'JSONDeserializer'))):
                    
                #     count = count+1

                #     val = msg.key().decode('utf-8')

                #     if t1=="IngestionTime":
                #         time1=int(msg.timestamp()[1])
                    
                #     else:
                #         mat = re.search(pattern,val)
                #         time1 = int(mat.group(1))

                    
                #     if t2 == 'IngestionTime':
                
                #         time2=int(msg.timestamp()[1])
                
                
                #     elif t2 == 'consumerWallClockTime':
                
                #         time2= time.time()*1000               
                    
                #     latency = (time2-time1)
                    
                #     latency_arry.append(latency)



    except KeyboardInterrupt:
        
        pass
    
    finally:
        
        consumer.close()

        n = datetime.now()
        
        date_string = n.strftime("%Y-%m-%d %H:%M:%S.%f")
        

        
        print("\nTotal Message read by consumer\t:\t",count)

        print("\nCurrent Time\t:\t",date_string)

        # with open('numbers.csv', 'w', newline='') as file:
        #   writer = csv.writer(file)

        #   # Write the array to the CSV file
        #   writer.writerow(latency_arry)

        if sampling == True:

            length = int(len(latency_arry)*.3)

            random_elements = random.sample(latency_arry,length)

            avg=sum(random_elements)//len(random_elements)

            print("\nNumber of message sampled(sampling enabled):\t\t",len(random_elements))

            print("\nAverage Latency in ms:\t\t\t",avg)


        elif sampling == False:

            avg = sum(latency_arry)//count

            print("\nNumber of messages sampled(sampling disabled):\t\t",count)

            print("\nAverage latency in ms:\t\t",avg)


        print("\n\nQuantiles of the latencies measured in ms:")


        quantiles = np.quantile(latency_arry, [.5, .9, .95, .99, .999])

        print("\n\t50th percerntile:\t",quantiles[0])

        print("\n\t90th percentile:\t",quantiles[1])

        print("\n\t95th percentile:\t",quantiles[2])

        print("\n\t99th percentile:\t",quantiles[3])

        print("\n\t99.9th percentile:",quantiles[4])
        

        if output_type == 'dumpToTopic':

          schema_string ="""
            {
              "namespace": "example.avro",
              "type": "record",
              "name": "result",
              "fields": [
                  {"name": "average", "type": "int"},
                  {"name": "percentile50", "type": "int"},
                  {"name": "percentile90", "type": "int"},
                  {"name": "percentile95", "type": "int"},
                  {"name": "percentile99", "type": "int"},
                  {"name": "percentile999", "type": "int"},
                  {"name": "Date_Time", "type": "string"}
              ]
            }
            """

          result = {
                    "average": int(avg),
                    "percentile50": int(quantiles[0]),
                    "percentile90": int(quantiles[1]),
                    "percentile95": int(quantiles[2]),
                    "percentile99": int(quantiles[3]),
                    "percentile999": int(quantiles[4]),
                    "Date_Time": str(date_string)
                  }


          schema_registry_client = SchemaRegistryClient(conf=read_ccloud_config(args.producer_config_file,'sr'))

          avro_serializer = AvroSerializer(schema_registry_client,schema_string)  

          producer=Producer(producer_properties)

          producer.produce(topic= output_topic,value=avro_serializer(result, SerializationContext( output_topic, MessageField.VALUE)))     


          # for i, element in enumerate(latency_arry):
          #   key = str(i)  # Convert the index to a string
          #   value = json.dumps(element)  # Convert the integer to a JSON string
          #   producer.produce(output_topic, key=key, value=value)
          #   #producer.produce('topic_6', key=i.to_bytes((count.bit_length() + 7)// 8, byteorder='big'), value=element.to_bytes((count.bit_length() + 7)// 8, byteorder='big'))

          # # Wait for any outstanding messages to be delivered and delivery reports to be received
          
          producer.flush()
          
          print("\n\nData written successfully to :\t",output_topic)

        
        if (output_type == 'localFileDump'):
                      
          df = pd.DataFrame({'average': [avg],
                   'quantile_50': quantiles[0],
                   'quantile_90': quantiles[1],
                   'quantile_90': quantiles[2],
                   'quantile_99': quantiles[3],
                   'quantile_99.9':quantiles[4],
                   'date_time':date_string})
            
          write_to_csv(local_filepath, df)

                       
        
        elif output_type == 'console':
            print(latency_arry)

        print("\n\n\t\t\t\t\t\t\t\t\t\t\tconsumer closing\n\n")
            
        
        


