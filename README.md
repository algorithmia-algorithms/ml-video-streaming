# video-streaming-service

Create your own video streaming service that leverages [Algorithmia](https://www.algorithmia.com) for ML processing. 
Take advantage of any image based ML algorithm on Algorithmia and process a live stream with it.

## Getting started
First you will need to have [Docker](https://www.docker.com/) installed and to a recent version, this package was created with version `19.03.8`.
Then, you should be ready to begin.

### Procedure
1. Create a `config.yaml` file, follow the [example.yaml]() file as a guide; please add your `algorithmia api key`, and your `aws api credentials`, if you're using aws STS, please define 'local_iam' and provide your profile name.
2. run `pip install -r requirements.txt` to ensure you have the proper dependencies to run everything.
3. If you want to run the whole stack on your local machine, simply run `python init.py` and wait for the system to start.
4. If you want to run the stack on multiple machines, run `python init.py generate`, `python init.py process`, `python init.py broadcast` on 3 different machines, they will be able to communicate with AWS Kinesis.
Finally, if all went well you should be able to visit http://localhost, which is proxied through your broadcast docker container running nginx and eventually your livestream will begin broadcasting.

If you'd like to cancel/close down your streaming pipeline, simply press "ctrl + c" which will automatically kill not only the python job, but all running docker containers.




