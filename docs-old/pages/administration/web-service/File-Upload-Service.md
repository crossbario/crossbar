title: File Upload Service
toc: [Documentation, Administration, Web Services, File Upload Service]

# File Upload Service

The **File Upload Service** allows uploading of files to a directory on the Crossbar.io node via (chunked) HTTP/POSTs.

> The file upload service has some issues, and may be removed in a future release. Use at your own risk!

Modern browsers [support](http://caniuse.com/#feat=fileapi) the [HTML5 File API](http://www.w3.org/TR/FileAPI/) which allows users to select files from their local system to be uploaded by the browser. This service can handle big files (GBs) and when combined with [Resumable.js](http://www.resumablejs.com/) features:

* upload one or multiple files
* chunked uploading
* select or drag & drop to upload
* resuming uploads
* progress indication via WAMP PubSub events




## Configuration

To configure a File Upload Service, attach a dictionary element to a path in your [Web transport](Web Transport and Services):


attribute | description
---|---
**`type`** | MUST be `"upload"` (*required*)
**`realm`** | The realm to which the service session associated with the resource will attach to. (*required*)
**`role`** | The role under which the service session associated with the resource will attach under. (*required*)
**`directory`** | The folder for completely uploaded files relative to the .crossbar folder in your crossbar node. (*required*)
**`temp_directory`** | A folder to hold incomplete uploads. Each incomplete upload will be a subfolder containing the uploaded file chunks. (*required*)
**`form_fields`** | Contains the form field mapping between client POST request and backend (*required*)
**`options.file_types`** | A JSON Array of permitted file extension strings including the dots.
**`options.file_permissions`** | The file access permissions to use for the completely uploaded files. (chmod octal code)
**`options.max_file_size`** | The maximally allowed file size in bytes to upload. Refers to the file not to the chunks of the file.

The `form_fields` dictionary contains the form field names that the client uses to upload files. It has the following configuration parameters:

```javascript
"form_fields": {
   "file_name": "resumableFilename",
   "mime_type": "resumableType",
   "total_size": "resumableTotalSize",
   "chunk_number": "resumableChunkNumber",
   "chunk_size": "resumableChunkSize",
   "total_chunks": "resumableTotalChunks",
   "content": "file",
   "on_progress": "on_progress",
   "session": "session",
   "chunk_extra": "chunk_extra",
   "finish_extra": "finish_extra"
}
```

attribute | description
---|---
**`file_name`** | The name of the form field containing the file name. (The file name is not used for anything in the backend). (*required*)
**`mime_type`** | The name of the form field to hold the MIME type of the uploaded file. (*required*)
**`total_size`** | The name of the form field to hold the integer representing the size of the file in bytes. (*required*)
**`chunk_number`** | The name of the form field to hold the chunk number of the current file chunk. (*required*)
**`chunk_size`** | The name of the form field holding the chunk size. (*required*)
**`total_chunks`** | The name of the form field holding the total number of chunks for the file to be transfered. Needs to be POSTed with every chunk. (*required*)
**`content`** | The name of the form field containing the file content. (*required*)
**`on_progress`** | Optional name of the form field containing the URI to publish upload related events to. If an URI is provided, progress events will be published as a file is being uploaded.
**`session`** | Optional name of the form field containing the WAMP session ID of the session to which publihed progress event should be restricted. If no session ID is provided, progress events can be received by any (authorized) session.
**`chunk_extra`** | The optional name of the form field to hold a serialized JSON object with custom information that will be sent on every chunk upload completion to any listening client.
**`finish_extra`** | The optional name of the form field to hold a serialized JSON object with custom information that will be sent on file upload completion to any listening client.

In the example above the file name is passsed to the backend in a POST multipart formdata field with name="myFilename")

```html
<input myFilename="test.csv" myprogress_uri="my.upload.progress.uri" />
```

---

## File Post processing

To trigger post processing of files on the server one solution would be to create a WAMP client on the server (e.g. a python component using autobahn-python) which subscribes to the upload topic specified under the form field name given in `on_progress`. This component then checks the progress payload for the key/value `status="finished"` and can also extract custom additional data sent along from the client in the propertie with name given by `finish_extra`. Upon reception of this event the component can fire off post processing of the file.

Another solution would be to use the python library [watchdog](https://pypi.python.org/pypi/watchdog) to watch on the upload folder. As long as the specified upload-temp folder and the upload folder reside on the same file system, the crossbar file uploader handles files such that all files are _moved_ into the upload folder which constitutes an atomic file system operation. Thereby no incompletely copied or downloaded files can be picked up by watchdog.

---

## Resumable Uploads

To implement resumable uploads crossbar file upload functionality provides a GET response on the same path. The response will either be with

* `Status 200` which indicates that the file or chunk of file is already pressent in the backend.
* A response with any other Status means the file/chunk is not yet present in the backend and should be uploaded.

With this service the upload client can check for existence of the chunk in the backend prior to POSTing the chunk. This effectively implements resumable uploads.

The GET response needs to have the same arguments as the POST request above.

---

## Example

We have a [complete example](https://github.com/crossbario/crossbarexamples/tree/master/fileupload) in the [Crossbar.io examples repository](https://github.com/crossbario/crossbarexamples) repository.

Clone the repo, change to the example folder `fileupload` and start Crossbar.io:

    crossbar start

To start Crossbar.io with debug log messages:

    crossbar start --loglevel=debug

Open [http://localhost:8080](http://localhost:8080) in your browser. Open the JavaScript console to see file upload progress events when uploading files. Then either click **Select files to upload** or drop files to **Drop files here to upload**. The uploaded files will appear within the `uploaded` subdirectory in the example folder.

The example uses this configuration:

```javascript
{
   "workers": [{
      "type": "router",
      ...
      "transports": [{
         "type": "web",
         ...
         "paths": {
            ...
            "upload": {
               "type": "upload",
               "realm": "realm1",
               "role": "anonymous",
               "directory": "../uploaded",
               "temp_directory": "../temp",
               "form_fields": {
                  "file_name": "resumableFilename",
                  "mime_type": "resumableType",
                  "total_size": "resumableTotalSize",
                  "chunk_number": "resumableChunkNumber",
                  "chunk_size": "resumableChunkSize",
                  "total_chunks": "resumableTotalChunks",
                  "content": "file",
                  "on_progress": "on_progress",
                  "session": "session",
                  "chunk_extra": "chunk_extra",
                  "finish_extra": "finish_extra"
               },
               "options": {
                  "max_file_size": 209715200,
                  "file_permissions": "0644",
                  "file_types": [".csv", ".txt", ".pdf", ".img"]
               }
            }
         }
      }]
   }]
}
```

---
