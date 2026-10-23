const json = (value, status = 200, headers = {}) => new Response(JSON.stringify(value), {
  status, headers: {"Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store", ...headers}
});

async function readPayload(request) {
  if (!request.headers.get("content-type")?.toLowerCase().startsWith("application/json")) throw new Error("content_type");
  if (Number(request.headers.get("content-length")) > 8192) throw new Error("too_large");
  const reader = request.body?.getReader();
  if (!reader) throw new Error("invalid");
  const chunks = []; let length = 0;
  while (true) {
    const {done, value} = await reader.read(); if (done) break;
    length += value.byteLength;
    if (length > 8192) { await reader.cancel(); throw new Error("too_large"); }
    chunks.push(value);
  }
  const bytes = new Uint8Array(length); let offset = 0;
  for (const part of chunks) { bytes.set(part, offset); offset += part.byteLength; }
  return JSON.parse(new TextDecoder("utf-8", {fatal: true}).decode(bytes));
}

export function validate(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("invalid");
  if (typeof value.request_id !== "string" || !/^[a-f0-9]{24}$/.test(value.request_id)) throw new Error("invalid");
  if (typeof value.message !== "string" || !value.message.trim() || value.message.length > 1500) throw new Error("invalid");
  if (!["bug", "suggestion", "other"].includes(value.category)) throw new Error("invalid");
  if (typeof value.contact !== "string" || value.contact.length > 100) throw new Error("invalid");
  if (typeof value.version !== "string" || !/^\d+\.\d+(?:\.\d+)?$/.test(value.version)) throw new Error("invalid");
  return {request_id:value.request_id, message:value.message.trim(), contact:value.contact.trim(), category:value.category, version:value.version};
}

async function discordCall(path, env, payload, fetcher, method = "POST") {
  const response = await fetcher("https://discord.com/api/v10" + path, {
    method, headers:{Authorization:"Bot " + env.DISCORD_BOT_TOKEN, "Content-Type":"application/json", "User-Agent":"DiscordBot (https://github.com/geujang/OTONova, 1.5)"},
    body:payload === undefined ? undefined : JSON.stringify(payload), signal:AbortSignal.timeout(8000)
  });
  if (response.status === 429) return {limited:true};
  if (!response.ok) {
    let data = {}; try {data = await response.json();} catch (_) {}
    const error = new Error("discord_delivery");
    error.provider_status = response.status;
    if (Number.isInteger(data.code)) error.provider_code = data.code;
    error.kind = response.status === 401 ? "bot_auth_failed" :
      data.code === 50278 ? "no_mutual_server" : data.code === 50007 ? "dm_unavailable" : data.code === 50001 ? "bot_access_denied" : "delivery_failed";
    throw error;
  }
  return response.json();
}

export function createWorker(fetcher = fetch) {
  return {async fetch(request, env) {
    const path = new URL(request.url).pathname;
    if (path !== "/feedback") return json({error:"not_found"},404);
    if (request.method !== "POST") return json({error:"method_not_allowed"},405,{Allow:"POST"});
    let input;
    try {input = validate(await readPayload(request));}
    catch(error) {return json({error:error.message === "too_large" ? "too_large" : "invalid_feedback"},400);}
    if (!env.DISCORD_BOT_TOKEN || !/^\d{16,22}$/.test(env.DISCORD_FORUM_CHANNEL_ID || "") ||
        !env.FEEDBACK_LIMITER || !env.TOTAL_LIMITER) return json({error:"not_configured"},503);
    try {
      // Network address is used transiently for throttling, never sent to Discord.
      const ip = request.headers.get("CF-Connecting-IP") || "unknown";
      if (!(await env.FEEDBACK_LIMITER.limit({key:ip})).success ||
          !(await env.TOTAL_LIMITER.limit({key:"feedback"})).success)
        return json({error:"rate_limited"},429,{"Retry-After":"60"});
      const channel = await discordCall(`/channels/${env.DISCORD_FORUM_CHANNEL_ID}`,env,undefined,fetcher,"GET");
      if (channel.limited) return json({error:"rate_limited"},429,{"Retry-After":"60"});
      if (channel.type !== 15 || channel.id !== env.DISCORD_FORUM_CHANNEL_ID) return json({error:"invalid_forum"},503);
      const labels = {bug:"오류 제보",suggestion:"기능 제안",other:"기타"};
      const tagNames = {bug:["오류 제보","오류","버그","bug"],suggestion:["기능 제안","제안","suggestion"],other:["기타","other"]};
      const tag = (channel.available_tags || []).find(t => tagNames[input.category].includes(t.name.toLowerCase()));
      if ((channel.flags & 16) && !tag) return json({error:"forum_tag_required"},503);
      const content = `[OTONova ${input.version}] ${labels[input.category]}\n` +
        (input.contact ? `Contact: ${input.contact}\n` : "") + `ID: ${input.request_id}\n\n${input.message}`;
      const title = input.message.replace(/\s+/g," ").replace(/[@#]/g,"").trim();
      const delivered = await discordCall(`/channels/${channel.id}/threads`,env,{
        name:`[${labels[input.category]}] ${title}`.slice(0,100),
        message:{content,allowed_mentions:{parse:[]}},
        ...(tag ? {applied_tags:[tag.id]} : {})
      },fetcher);
      if (delivered.limited) return json({error:"rate_limited"},429,{"Retry-After":"60"});
      if (!delivered.id || !delivered.message?.id) throw new Error("discord_message");
      return json({ok:true,request_id:input.request_id});
    } catch (error) {
      const kind = ["bot_auth_failed","dm_unavailable","bot_access_denied","no_mutual_server"].includes(error.kind) ? error.kind : "delivery_failed";
      return json({error:kind,provider_status:error.provider_status,provider_code:error.provider_code},502);
    }
  }};
}
export default createWorker();
