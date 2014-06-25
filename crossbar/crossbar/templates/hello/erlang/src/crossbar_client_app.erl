%% do with this code what ever you like
%% Bas Wegh

%% @private
-module(crossbar_client_app).
-behaviour(application).

%% API.
-export([start/2]).
-export([stop/1]).

%% API.

start(_Type, _Args) ->
  crossbar_client:start_link().

stop(_State) ->
	ok.
