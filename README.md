# video-streaming-service

Create your own video streaming service that leverages [Algorithmia](https://www.algorithmia.com) for ML processing. 
Take advantage of any image based ML algorithm on Algorithmia and process a live stream with it.

## Getting started
First you will need to have [Docker](https://www.docker.com/) installed and to a recent version, this package was created with version `19.03.8`.
Then, you should be ready to begin.

### Procedure
1. Create a `config.yaml` file, follow the [example.yaml]() file as a guide; please add your `algorithmia api key`, and your `aws api credentials`.
2. Run the following docker command `docker build -f Dockerfile -t stream-processing .` and wait for that to complete.
3. Start the generator process with `docker run --rm --env MODE=generate stream-processing`, you can test everything is working by adding the `-it` argument.
4. Start the processor process with `docker run --rm --env MODE=process stream-processing`, this one is worth attaching to when verifying scaling,etc
5. and finally you'll want to start the broadcast process with `docker run --rm -p 1560:80 --env MODE=broadcast stream-processing`
Now you should be able to visit http://localhost:1560, which is proxied through your broadcast docker container running nginx.


