%% do with this code what ever you like
%% Bas Wegh

%% @private
-module(simple_client_app).
-behaviour(application).

%% API.
-export([start/2]).
-export([stop/1]).

%% API.

start(_Type, _Args) ->
  simple_client:start_link().

stop(_State) ->
	ok.
