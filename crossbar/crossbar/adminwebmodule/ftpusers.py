###############################################################################
##
##  Copyright (C) 2011-2013 Tavendo GmbH
##
##  This program is free software: you can redistribute it and/or modify
##  it under the terms of the GNU Affero General Public License, version 3,
##  as published by the Free Software Foundation.
##
##  This program is distributed in the hope that it will be useful,
##  but WITHOUT ANY WARRANTY; without even the implied warranty of
##  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
##  GNU Affero General Public License for more details.
##
##  You should have received a copy of the GNU Affero General Public License
##  along with this program. If not, see <http://www.gnu.org/licenses/>.
##
###############################################################################


import os, shutil, sys

from twisted.python import log

from autobahn.wamp import exportRpc
from autobahn.util import utcstr, utcnow, parseutc, newid

from crossbar.adminwebmodule.uris import *


class FtpUsers:
   """
   FTP users model.
   """

   FTPUSER_USER_PATTERN = "^[a-z0-9_\-]*$"
   FTPUSER_USER_MIN_LENGTH = 3
   FTPUSER_USER_MAX_LENGTH = 15

   FTPUSER_PASSWORD_PATTERN = "^[a-zA-Z0-9_\-!$%&/=]*$"
   FTPUSER_PASSWORD_MIN_LENGTH = 6
   FTPUSER_PASSWORD_MAX_LENGTH = 20

   FTPUSER_LABEL_MIN_LENGTH = 3
   FTPUSER_LABEL_MAX_LENGTH = 20


   def __init__(self, proto):
      """
      :param proto: WAMP protocol class this model is exposed from.
      :type proto: Instance of AdminWebSocketProtocol.
      """
      self.proto = proto


   def _createFtpDir(self, user):
      ftp_base_dir = str(self.proto.factory.services["config"].get("ftp-dir"))
      if not os.path.isdir(ftp_base_dir):
         os.mkdir(ftp_base_dir)
         log.msg("FTP base directory %s created" % ftp_base_dir)

      ftp_dir = os.path.join(ftp_base_dir, user)
      if not os.path.isdir(ftp_dir):
         os.mkdir(ftp_dir)

         log_dir = self.proto.factory.services["config"].get("log-dir")
         n = 0
         for root, dirs, files in os.walk(log_dir):
            for f in files:
               sourcepath = os.path.join(root, f)
               targetpath = os.path.join(ftp_dir, f)

               # http://bugs.python.org/issue8879
               if sys.platform.startswith("win"):
                  # FIXME: this is not correct, will only work for files
                  # that are not modified thereafter!!
                  shutil.copyfile(sourcepath, targetpath)
               else:
                  os.link(sourcepath, targetpath)

               n += 1

         log.msg("FTP directory %s created, hard linked %d log files" % (ftp_dir, n))


   def _removeFtpDir(self, user):
      ftp_dir = os.path.join(self.proto.factory.services["config"].get("ftp-dir"), user)
      if os.path.isdir(ftp_dir):
         shutil.rmtree(ftp_dir, True)
         log.msg("FTP directory %s removed" % ftp_dir)


   def _moveFtpDir(self, olduser, newuser):
      ftp_dir_old = os.path.join(self.proto.factory.services["config"].get("ftp-dir"), olduser)
      ftp_dir_new = os.path.join(self.proto.factory.services["config"].get("ftp-dir"), newuser)
      shutil.move(ftp_dir_old, ftp_dir_new)
      log.msg("FTP directory %s moved to %s" % (ftp_dir_old, ftp_dir_new))


   def _createFtpUser(self, txn, spec):
      """
      Create new FTP user, runs in database transaction.
      """
      attrs = {"label": (True,
                         [str, unicode],
                         FtpUsers.FTPUSER_LABEL_MIN_LENGTH,
                         FtpUsers.FTPUSER_LABEL_MAX_LENGTH,
                         None),
               "user": (True,
                        [str, unicode],
                        FtpUsers.FTPUSER_USER_MIN_LENGTH,
                        FtpUsers.FTPUSER_USER_MAX_LENGTH,
                        FtpUsers.FTPUSER_USER_PATTERN),
               "password": (True,
                            [str, unicode],
                            FtpUsers.FTPUSER_PASSWORD_MIN_LENGTH,
                            FtpUsers.FTPUSER_PASSWORD_MAX_LENGTH,
                            FtpUsers.FTPUSER_PASSWORD_PATTERN)}

      errcnt, errs = self.proto.checkDictArg("ftpuser spec", spec, attrs)

      txn.execute("SELECT created FROM ftpuser WHERE user = ?", [spec["user"]])
      if txn.fetchone() is not None:
         errs["user"].append((self.proto.shrink(URI_ERROR + "duplicate-value"), "FTP user '%s' already exists" % spec["user"]))
         errcnt += 1

      if errcnt:
         raise Exception(URI_ERROR + "illegal-argument", "one or more illegal arguments (%d errors)" % errcnt, errs)

      try:
         user = str(spec["user"])
         #self._createFtpDir(user)
      except Exception, e:
         msg = "could not create FTP dir for new FTP user '%s' (%s)" % (user, str(e))
         log.msg(msg)
         raise Exception(msg)

      id = newid()
      ftpuser_uri = URI_FTPUSER + id
      label = spec["label"].strip()
      now = utcnow()
      txn.execute("INSERT INTO ftpuser (id, label, user, created, password) VALUES (?, ?, ?, ?, ?)",
                  [id,
                   label,
                   spec["user"],
                   now,
                   spec["password"]])

      ftpuser = {"uri": ftpuser_uri,
                 "created": now,
                 "label": label,
                 "user": spec["user"],
                 "password": spec["password"]}

      self.proto.dispatch(URI_EVENT + "on-ftpuser-created", ftpuser, [self.proto])

      ftpuser["uri"] = self.proto.shrink(ftpuser_uri)
      return ftpuser


   @exportRpc("create-ftpuser")
   def createFtpUser(self, spec):
      """
      Create new FTP user.

      Parameters:

         spec:             FTP user specification, a dictionary.
         spec[]
            label:         Label, a string, not necessarily unique.
            user:          User, a string, must be unique.
            password:      Password, a string.

      Result:

         {"uri":        <FtpUser URI>,
          "created":    <FtpUser creation timestamp>,
          "label":      <FtpUser label>,
          "user":       <FtpUser user>,
          "password":   <FtpUser password>}

      Events:

         on-ftpuser-created

      Errors:

         spec:                   illegal-argument

         spec[]:

            *:                   illegal-attribute-type,
                                 missing-attribute

            label,
            user,
            password:            attribute-value-too-short,
                                 attribute-value-too-long

            user,
            password:            attribute-value-invalid-characters

            user:                duplicate-value

            ?:                   unknown-attribute
      """
      return self.proto.dbpool.runInteraction(self._createFtpUser, spec)


   def _deleteFtpUser(self, txn, ftpUserUri):

      if type(ftpUserUri) not in [str, unicode]:
         raise Exception(URI_ERROR + "illegal-argument", "Expected type str/unicode for agument ftpUserUri, but got %s" % str(type(ftpUserUri)))

      uri = self.proto.resolveOrPass(ftpUserUri)
      id = self.proto.uriToId(uri)

      txn.execute("SELECT user FROM ftpuser WHERE id = ?", [id])
      res = txn.fetchone()
      if res is not None:

         try:
            user = str(res[0])
            #self._removeFtpDir(user)
         except Exception, e:
            msg = "could not remove FTP dir for deleted FTP user '%s' (%s)" % (user, str(e))
            log.msg(msg)
            raise Exception(msg)

         txn.execute("DELETE FROM ftpuser WHERE id = ?", [id])

         self.proto.dispatch(URI_EVENT + "on-ftpuser-deleted", uri, [self.proto])

         return self.proto.shrink(uri)

      else:
         raise Exception(URI_ERROR + "no-such-object", "No FTP user with URI %s" % uri)


   @exportRpc("delete-ftpuser")
   def deleteAppCred(self, ftpUserUri):
      """
      Delete an FTP user.

      Parameters:

         ftpUserUri:          URI or CURIE of FTP user to delete.

      Result:

         <FTP User URI>

      Events:

         on-ftpuser-deleted

      Errors:

         ftpUserUri:             illegal-argument,
                                 no-such-object
      """
      return self.proto.dbpool.runInteraction(self._deleteFtpUser, ftpUserUri)


   def _modifyFtpUser(self, txn, ftpUserUri, specDelta):

      if type(ftpUserUri) not in [str, unicode]:
         raise Exception(URI_ERROR + "illegal-argument", "Expected type str/unicode for argument ftpUserUri, but got %s" % str(type(ftpUserUri)))

      uri = self.proto.resolveOrPass(ftpUserUri)
      id = self.proto.uriToId(uri)

      txn.execute("SELECT label, user, password FROM ftpuser WHERE id = ?", [id])
      res = txn.fetchone()

      if res is not None:

         attrs = {"label": (False,
                            [str, unicode],
                            FtpUsers.FTPUSER_LABEL_MIN_LENGTH,
                            FtpUsers.FTPUSER_LABEL_MAX_LENGTH,
                            None),
                  "user": (False,
                           [str, unicode],
                           FtpUsers.FTPUSER_USER_MIN_LENGTH,
                           FtpUsers.FTPUSER_USER_MAX_LENGTH,
                           FtpUsers.FTPUSER_USER_PATTERN),
                  "password": (False,
                               [str, unicode],
                               FtpUsers.FTPUSER_PASSWORD_MIN_LENGTH,
                               FtpUsers.FTPUSER_PASSWORD_MAX_LENGTH,
                               FtpUsers.FTPUSER_PASSWORD_PATTERN)}

         errcnt, errs = self.proto.checkDictArg("ftpuser delta spec", specDelta, attrs)

         now = utcnow()
         delta = {}
         sql = "modified = ?"
         sql_vars = [now]

         if specDelta.has_key("label"):
            newval = specDelta["label"].strip()
            if newval != res[0]:
               delta["label"] = newval
               sql += ", label = ?"
               sql_vars.append(newval)

         if specDelta.has_key("user"):
            newval = specDelta["user"].strip()
            if newval != res[1]:
               txn.execute("SELECT created FROM ftpuser WHERE user = ?", [newval])
               if txn.fetchone() is not None:
                  errs["user"].append((self.proto.shrink(URI_ERROR + "duplicate-value"), "FTP user '%s' already exists" % newval))
               delta["user"] = newval
               sql += ", user = ?"
               sql_vars.append(newval)

         if specDelta.has_key("password"):
            newval = specDelta["password"]
            if newval != res[2]:
               delta["password"] = newval
               sql += ", password = ?"
               sql_vars.append(newval)

         if errcnt:
            raise Exception(URI_ERROR + "illegal-argument", "one or more illegal arguments (%d errors)" % errcnt, errs)

         if len(delta) > 0:

            ## move FTP directory when 'user' has changed
            ##
            olduser = str(res[1])
            newuser = str(delta.get("user", olduser))
            if newuser != olduser:
               try:
                  pass
                  #self._moveFtpDir(olduser, newuser)
               except:
                  msg = "could not move FTP dir for FTP user '%s' to '%s' (%s)" % (olduser, newuser, str(e))
                  log.msg(msg)
                  raise Exception(msg)

            delta["modified"] = now
            delta["uri"] = uri

            sql_vars.append(id)
            txn.execute("UPDATE ftpuser SET %s WHERE id = ?" % sql, sql_vars)

            self.proto.dispatch(URI_EVENT + "on-ftpuser-modified", delta, [self.proto])

            delta["uri"] = self.proto.shrink(uri)
            return delta
         else:
            return {}

      else:
         raise Exception(URI_ERROR + "no-such-object", "No FTP user with URI %s" % uri)


   @exportRpc("modify-ftpuser")
   def modifyFtpUser(self, ftpUserUri, specDelta):
      """
      Modify existing FTP user.

      Parameters:

         ftpUserUri:          URI or CURIE of FTP user to modify.
         specDelta:           FTP user change specification, a dictionary.
         specDelta[]:
            label:            Label, a string, not necessarily unique.
            user:             User, a string, must be unique.
            password:         Password, a string.

      Result:

         {"uri":           <FTP User URI>,
          "modified":      <FTP User modification timestamp>,
          "label":         <FTP User label>,
          "user":          <FTP User user>,
          "password":      <FTP User password>}

      Events:

         on-ftpuser-modified

      Errors:

         ftpUserUri,
         specDelta:              illegal-argument

         ftpUserUri:             no-such-object

         specDelta[]:

            *:                   illegal-attribute-type,
                                 missing-attribute

            label,
            user,
            password:            attribute-value-too-short,
                                 attribute-value-too-long

            user,
            password:            attribute-value-invalid-characters

            user:                duplicate-value

            ?:                   unknown-attribute
      """
      return self.proto.dbpool.runInteraction(self._modifyFtpUser, ftpUserUri, specDelta)


   @exportRpc("get-ftpusers")
   def getFtpUsers(self):
      """
      Return list of FTP users (ordered by label/user ascending).
      """
      d = self.proto.dbpool.runQuery("SELECT id, created, modified, label, user, password FROM ftpuser ORDER BY label, user ASC")
      d.addCallback(lambda res: [{"uri": self.proto.shrink(URI_FTPUSER + r[0]),
                                  "created": r[1],
                                  "modified": r[2],
                                  "label": r[3],
                                  "user": r[4],
                                  "password": r[5]} for r in res])
      return d
