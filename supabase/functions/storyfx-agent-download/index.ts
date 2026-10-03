import { createHandler } from "./handler.ts";
import { createResolver } from "./release_catalog.ts";

Deno.serve(createHandler(createResolver((name) => Deno.env.get(name))));
