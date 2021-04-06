/// A key store is providing access to user key pairs for management realms on CFC.
var KeyStore = function (storage, key) {
    var self = this;

    self.storage = storage;

    // they key in local storage under which we save the key store
    self.key = key || "com.crossbario.fabric.keystore";
};

/// Save key store to local storage.
KeyStore.prototype.init = function (user_email) {
    var self = this;

        // if not found, create a initial data structure
        self._init(user_email);

        // and save it in local storage
        self.save();
}


/// Save key store to local storage.
KeyStore.prototype._init = function (user_email) {
    var self = this;

    // FIXME: ask user for email!
    var _user_email = user_email || 'tobias.oberstein@gmail.com';

    // gemerate new key seed
    var _user_key = autobahn.nacl.randomBytes(autobahn.nacl.sign.seedLength);

    // set user data object
    self.data = {
        user_email: _user_email,
        user_key: autobahn.util.btoa(_user_key),
        user_key_status: 'unverified'
    };
};


/// Save key store to local storage.
KeyStore.prototype.erase = function () {
    var self = this;

    self.data = null;
    self.storage.setItem(self.key, autobahn.nacl.randomBytes(8*1024));
    self.storage.setItem(self.key, null);

    console.log('key store erased!');
};


/// Save key store to local storage.
KeyStore.prototype.save = function () {
    var self = this;

    self.storage.setItem(self.key, JSON.stringify(self.data));

    console.log('key store saved!');
};


/// Load key store from local storage.
KeyStore.prototype.load = function () {
    var self = this;

    var data = self.storage.getItem(self.key);
    console.log('ccc', data, self.key);
    if (data && data.length > 0) {
        self.data = JSON.parse(data);
        console.log(data, self.data);
        if (self.data.user_key) {
            self.data.user_key = autobahn.util.atob(self.data.user_key);
        }
        console.log('key store loaded');
        return self.data;
    } else {
        return null;
    }
};


/// Get user email.
KeyStore.prototype.user_email = function () {
    var self = this;

    if (self.data && self.data.user_email) {
        return self.data.user_email;
    } else {
        return null;
    }
};


/// Get user key.
KeyStore.prototype.user_key = function () {
    var self = this;

    if (self.data && self.data.user_key) {
        return autobahn.nacl.sign.keyPair.fromSeed(self.data.user_key);
    } else {
        return null;
    }
};


/// Get user key status.
KeyStore.prototype.user_key_status = function () {
    var self = this;

    if (self.data && self.data.user_key_status) {
        return self.data.user_key_status;
    } else {
        return null;
    }
};

console.log('KeyStore:', KeyStore);
