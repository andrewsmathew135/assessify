/**
 * Cloudflare Worker that fronts the FastAPI backend running in a Container.
 *
 * Cloudflare Containers are managed through a Durable Object that extends the
 * `Container` helper. This Worker simply forwards every incoming request to the
 * container instance, which serves the FastAPI app on port 8080.
 *
 * Deploy with:  npx wrangler deploy
 */
import { Container, getContainer } from "@cloudflare/containers";

export class Backend extends Container {
  // The port uvicorn listens on inside the container (see Dockerfile).
  defaultPort = 8080;
  // Scale-to-zero: stop the instance after a period of inactivity.
  sleepAfter = "15m";
}

interface Env {
  BACKEND: DurableObjectNamespace<Backend>;
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    // Route all traffic to a single shared container instance. For higher
    // throughput you can shard by a key (e.g. per-tenant) instead.
    const container = getContainer(env.BACKEND);
    return container.fetch(request);
  },
};
