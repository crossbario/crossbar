%% do with this code what ever you like
%% Bas Wegh

%% @private
-module(crossbar_client_sup).
-behaviour(supervisor).

%% API.
-export([start_link/0]).

%% supervisor.
-export([init/1]).

%% API.

-spec start_link() -> {ok, pid()}.
start_link() ->
  supervisor:start_link( ?MODULE, []).

%% supervisor.

init([]) ->
  Procs = [{crossbar_client,{crossbar_client,start_link,[]},permanent,5000,worker,[]}],
  {ok, {{one_for_one, 10, 10}, Procs}}.
