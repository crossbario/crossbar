title: File Upload Service toc: [Documentation, Administration, Web
Services, File Upload Service]

File Upload Service
===================

The **File Upload Service** allows uploading of files to a directory on
the Crossbar.io node via (chunked) HTTP/POSTs.

    The file upload service has some issues, and may be removed in a
    future release. Use at your own risk!

Modern browsers `support <http://caniuse.com/#feat=fileapi>`__ the
`HTML5 File API <http://www.w3.org/TR/FileAPI/>`__ which allows users to
select files from their local system to be uploaded by the browser. This
service can handle big files (GBs) and when combined with
`Resumable.js <http://www.resumablejs.com/>`__ features:

-  upload one or multiple files
-  chunked uploading
-  select or drag & drop to upload
-  resuming uploads
-  progress indication via WAMP PubSub events

Configuration
-------------

To configure a File Upload Service, attach a dictionary element to a
path in your `Web transport <Web%20Transport%20and%20Services>`__:

+------+------+
| attr | desc |
| ibut | ript |
| e    | ion  |
+======+======+
| **`` | MUST |
| type | be   |
| ``** | ``"u |
|      | ploa |
|      | d"`` |
|      | (*re |
|      | quir |
|      | ed*) |
+------+------+
| **`` | The  |
| real | real |
| m``* | m    |
| *    | to   |
|      | whic |
|      | h    |
|      | the  |
|      | serv |
|      | ice  |
|      | sess |
|      | ion  |
|      | asso |
|      | ciat |
|      | ed   |
|      | with |
|      | the  |
|      | reso |
|      | urce |
|      | will |
|      | atta |
|      | ch   |
|      | to.  |
|      | (*re |
|      | quir |
|      | ed*) |
+------+------+
| **`` | The  |
| role | role |
| ``** | unde |
|      | r    |
|      | whic |
|      | h    |
|      | the  |
|      | serv |
|      | ice  |
|      | sess |
|      | ion  |
|      | asso |
|      | ciat |
|      | ed   |
|      | with |
|      | the  |
|      | reso |
|      | urce |
|      | will |
|      | atta |
|      | ch   |
|      | unde |
|      | r.   |
|      | (*re |
|      | quir |
|      | ed*) |
+------+------+
| **`` | The  |
| dire | fold |
| ctor | er   |
| y``* | for  |
| *    | comp |
|      | lete |
|      | ly   |
|      | uplo |
|      | aded |
|      | file |
|      | s    |
|      | rela |
|      | tive |
|      | to   |
|      | the  |
|      | .cro |
|      | ssba |
|      | r    |
|      | fold |
|      | er   |
|      | in   |
|      | your |
|      | cros |
|      | sbar |
|      | node |
|      | .    |
|      | (*re |
|      | quir |
|      | ed*) |
+------+------+
| **`` | A    |
| temp | fold |
| _dir | er   |
| ecto | to   |
| ry`` | hold |
| **   | inco |
|      | mple |
|      | te   |
|      | uplo |
|      | ads. |
|      | Each |
|      | inco |
|      | mple |
|      | te   |
|      | uplo |
|      | ad   |
|      | will |
|      | be a |
|      | subf |
|      | olde |
|      | r    |
|      | cont |
|      | aini |
|      | ng   |
|      | the  |
|      | uplo |
|      | aded |
|      | file |
|      | chun |
|      | ks.  |
|      | (*re |
|      | quir |
|      | ed*) |
+------+------+
| **`` | Cont |
| form | ains |
| _fie | the  |
| lds` | form |
| `**  | fiel |
|      | d    |
|      | mapp |
|      | ing  |
|      | betw |
|      | een  |
|      | clie |
|      | nt   |
|      | POST |
|      | requ |
|      | est  |
|      | and  |
|      | back |
|      | end  |
|      | (*re |
|      | quir |
|      | ed*) |
+------+------+
| **`` | A    |
| opti | JSON |
| ons. | Arra |
| file | y    |
| _typ | of   |
| es`` | perm |
| **   | itte |
|      | d    |
|      | file |
|      | exte |
|      | nsio |
|      | n    |
|      | stri |
|      | ngs  |
|      | incl |
|      | udin |
|      | g    |
|      | the  |
|      | dots |
|      | .    |
+------+------+
| **`` | The  |
| opti | file |
| ons. | acce |
| file | ss   |
| _per | perm |
| miss | issi |
| ions | ons  |
| ``** | to   |
|      | use  |
|      | for  |
|      | the  |
|      | comp |
|      | lete |
|      | ly   |
|      | uplo |
|      | aded |
|      | file |
|      | s.   |
|      | (chm |
|      | od   |
|      | octa |
|      | l    |
|      | code |
|      | )    |
+------+------+
| **`` | The  |
| opti | maxi |
| ons. | mall |
| max_ | y    |
| file | allo |
| _siz | wed  |
| e``* | file |
| *    | size |
|      | in   |
|      | byte |
|      | s    |
|      | to   |
|      | uplo |
|      | ad.  |
|      | Refe |
|      | rs   |
|      | to   |
|      | the  |
|      | file |
|      | not  |
|      | to   |
|      | the  |
|      | chun |
|      | ks   |
|      | of   |
|      | the  |
|      | file |
|      | .    |
+------+------+

The ``form_fields`` dictionary contains the form field names that the
client uses to upload files. It has the following configuration
parameters:

.. code:: javascript

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

+------+------+
| attr | desc |
| ibut | ript |
| e    | ion  |
+======+======+
| **`` | The  |
| file | name |
| _nam | of   |
| e``* | the  |
| *    | form |
|      | fiel |
|      | d    |
|      | cont |
|      | aini |
|      | ng   |
|      | the  |
|      | file |
|      | name |
|      | .    |
|      | (The |
|      | file |
|      | name |
|      | is   |
|      | not  |
|      | used |
|      | for  |
|      | anyt |
|      | hing |
|      | in   |
|      | the  |
|      | back |
|      | end) |
|      | .    |
|      | (*re |
|      | quir |
|      | ed*) |
+------+------+
| **`` | The  |
| mime | name |
| _typ | of   |
| e``* | the  |
| *    | form |
|      | fiel |
|      | d    |
|      | to   |
|      | hold |
|      | the  |
|      | MIME |
|      | type |
|      | of   |
|      | the  |
|      | uplo |
|      | aded |
|      | file |
|      | .    |
|      | (*re |
|      | quir |
|      | ed*) |
+------+------+
| **`` | The  |
| tota | name |
| l_si | of   |
| ze`` | the  |
| **   | form |
|      | fiel |
|      | d    |
|      | to   |
|      | hold |
|      | the  |
|      | inte |
|      | ger  |
|      | repr |
|      | esen |
|      | ting |
|      | the  |
|      | size |
|      | of   |
|      | the  |
|      | file |
|      | in   |
|      | byte |
|      | s.   |
|      | (*re |
|      | quir |
|      | ed*) |
+------+------+
| **`` | The  |
| chun | name |
| k_nu | of   |
| mber | the  |
| ``** | form |
|      | fiel |
|      | d    |
|      | to   |
|      | hold |
|      | the  |
|      | chun |
|      | k    |
|      | numb |
|      | er   |
|      | of   |
|      | the  |
|      | curr |
|      | ent  |
|      | file |
|      | chun |
|      | k.   |
|      | (*re |
|      | quir |
|      | ed*) |
+------+------+
| **`` | The  |
| chun | name |
| k_si | of   |
| ze`` | the  |
| **   | form |
|      | fiel |
|      | d    |
|      | hold |
|      | ing  |
|      | the  |
|      | chun |
|      | k    |
|      | size |
|      | .    |
|      | (*re |
|      | quir |
|      | ed*) |
+------+------+
| **`` | The  |
| tota | name |
| l_ch | of   |
| unks | the  |
| ``** | form |
|      | fiel |
|      | d    |
|      | hold |
|      | ing  |
|      | the  |
|      | tota |
|      | l    |
|      | numb |
|      | er   |
|      | of   |
|      | chun |
|      | ks   |
|      | for  |
|      | the  |
|      | file |
|      | to   |
|      | be   |
|      | tran |
|      | sfer |
|      | ed.  |
|      | Need |
|      | s    |
|      | to   |
|      | be   |
|      | POST |
|      | ed   |
|      | with |
|      | ever |
|      | y    |
|      | chun |
|      | k.   |
|      | (*re |
|      | quir |
|      | ed*) |
+------+------+
| **`` | The  |
| cont | name |
| ent` | of   |
| `**  | the  |
|      | form |
|      | fiel |
|      | d    |
|      | cont |
|      | aini |
|      | ng   |
|      | the  |
|      | file |
|      | cont |
|      | ent. |
|      | (*re |
|      | quir |
|      | ed*) |
+------+------+
| **`` | Opti |
| on_p | onal |
| rogr | name |
| ess` | of   |
| `**  | the  |
|      | form |
|      | fiel |
|      | d    |
|      | cont |
|      | aini |
|      | ng   |
|      | the  |
|      | URI  |
|      | to   |
|      | publ |
|      | ish  |
|      | uplo |
|      | ad   |
|      | rela |
|      | ted  |
|      | even |
|      | ts   |
|      | to.  |
|      | If   |
|      | an   |
|      | URI  |
|      | is   |
|      | prov |
|      | ided |
|      | ,    |
|      | prog |
|      | ress |
|      | even |
|      | ts   |
|      | will |
|      | be   |
|      | publ |
|      | ishe |
|      | d    |
|      | as a |
|      | file |
|      | is   |
|      | bein |
|      | g    |
|      | uplo |
|      | aded |
|      | .    |
+------+------+
| **`` | Opti |
| sess | onal |
| ion` | name |
| `**  | of   |
|      | the  |
|      | form |
|      | fiel |
|      | d    |
|      | cont |
|      | aini |
|      | ng   |
|      | the  |
|      | WAMP |
|      | sess |
|      | ion  |
|      | ID   |
|      | of   |
|      | the  |
|      | sess |
|      | ion  |
|      | to   |
|      | whic |
|      | h    |
|      | publ |
|      | ihed |
|      | prog |
|      | ress |
|      | even |
|      | t    |
|      | shou |
|      | ld   |
|      | be   |
|      | rest |
|      | rict |
|      | ed.  |
|      | If   |
|      | no   |
|      | sess |
|      | ion  |
|      | ID   |
|      | is   |
|      | prov |
|      | ided |
|      | ,    |
|      | prog |
|      | ress |
|      | even |
|      | ts   |
|      | can  |
|      | be   |
|      | rece |
|      | ived |
|      | by   |
|      | any  |
|      | (aut |
|      | hori |
|      | zed) |
|      | sess |
|      | ion. |
+------+------+
| **`` | The  |
| chun | opti |
| k_ex | onal |
| tra` | name |
| `**  | of   |
|      | the  |
|      | form |
|      | fiel |
|      | d    |
|      | to   |
|      | hold |
|      | a    |
|      | seri |
|      | aliz |
|      | ed   |
|      | JSON |
|      | obje |
|      | ct   |
|      | with |
|      | cust |
|      | om   |
|      | info |
|      | rmat |
|      | ion  |
|      | that |
|      | will |
|      | be   |
|      | sent |
|      | on   |
|      | ever |
|      | y    |
|      | chun |
|      | k    |
|      | uplo |
|      | ad   |
|      | comp |
|      | leti |
|      | on   |
|      | to   |
|      | any  |
|      | list |
|      | enin |
|      | g    |
|      | clie |
|      | nt.  |
+------+------+
| **`` | The  |
| fini | opti |
| sh_e | onal |
| xtra | name |
| ``** | of   |
|      | the  |
|      | form |
|      | fiel |
|      | d    |
|      | to   |
|      | hold |
|      | a    |
|      | seri |
|      | aliz |
|      | ed   |
|      | JSON |
|      | obje |
|      | ct   |
|      | with |
|      | cust |
|      | om   |
|      | info |
|      | rmat |
|      | ion  |
|      | that |
|      | will |
|      | be   |
|      | sent |
|      | on   |
|      | file |
|      | uplo |
|      | ad   |
|      | comp |
|      | leti |
|      | on   |
|      | to   |
|      | any  |
|      | list |
|      | enin |
|      | g    |
|      | clie |
|      | nt.  |
+------+------+

In the example above the file name is passsed to the backend in a POST
multipart formdata field with name="myFilename")

.. code:: html

    <input myFilename="test.csv" myprogress_uri="my.upload.progress.uri" />

--------------

File Post processing
--------------------

To trigger post processing of files on the server one solution would be
to create a WAMP client on the server (e.g. a python component using
autobahn-python) which subscribes to the upload topic specified under
the form field name given in ``on_progress``. This component then checks
the progress payload for the key/value ``status="finished"`` and can
also extract custom additional data sent along from the client in the
propertie with name given by ``finish_extra``. Upon reception of this
event the component can fire off post processing of the file.

Another solution would be to use the python library
`watchdog <https://pypi.python.org/pypi/watchdog>`__ to watch on the
upload folder. As long as the specified upload-temp folder and the
upload folder reside on the same file system, the crossbar file uploader
handles files such that all files are *moved* into the upload folder
which constitutes an atomic file system operation. Thereby no
incompletely copied or downloaded files can be picked up by watchdog.

--------------

Resumable Uploads
-----------------

To implement resumable uploads crossbar file upload functionality
provides a GET response on the same path. The response will either be
with

-  ``Status 200`` which indicates that the file or chunk of file is
   already pressent in the backend.
-  A response with any other Status means the file/chunk is not yet
   present in the backend and should be uploaded.

With this service the upload client can check for existence of the chunk
in the backend prior to POSTing the chunk. This effectively implements
resumable uploads.

The GET response needs to have the same arguments as the POST request
above.

--------------

Example
-------

We have a `complete
example <https://github.com/crossbario/crossbarexamples/tree/master/fileupload>`__
in the `Crossbar.io examples
repository <https://github.com/crossbario/crossbarexamples>`__
repository.

Clone the repo, change to the example folder ``fileupload`` and start
Crossbar.io:

::

    crossbar start

To start Crossbar.io with debug log messages:

::

    crossbar start --loglevel=debug

Open http://localhost:8080 in your browser. Open the JavaScript console
to see file upload progress events when uploading files. Then either
click **Select files to upload** or drop files to **Drop files here to
upload**. The uploaded files will appear within the ``uploaded``
subdirectory in the example folder.

The example uses this configuration:

.. code:: javascript

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

--------------
