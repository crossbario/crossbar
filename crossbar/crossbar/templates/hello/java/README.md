# Running the jawampa Crossbar.io hello app

## Requirements

You will need:

* Java JDK >= 6
* [Apache Maven](http://maven.apache.org/)
* [jawampa](https://github.com/Matthias247/jawampa)

To install JDK and Maven on Ubuntu:

```
sudo apt-get install -y default-jdk maven
```

To install jawampa:

```
cd /tmp
git clone https://github.com/Matthias247/jawampa.git
cd jawampa
git checkout 0.1
mvn install
```

## Building the demo

To build the demo:

```
mvn dependency:copy-dependencies
mvn compile
```

## Running the demo

Now start Crossbar.io

```
crossbar start
```

and open your browser at [http://127.0.0.1:8080](http://127.0.0.1:8080) and watch the JavaScript console.
