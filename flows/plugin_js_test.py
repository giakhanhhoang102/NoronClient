from flowlite import Flow, step, finalize, expect, js

flow = Flow("plugin_js_test").debug(trace=True)

@step("call_js")
def call_js(ctx):
    obj = js.run("echo.js", {"hello": "world", "n": 123})
    expect.truthy(obj.get("ok"))
    ctx.echo = obj["echo"]

@finalize
def done(ctx):
    return {"echo": ctx.echo, "task_trace_len": len(ctx.meta.get("task_trace", []))}

flow.register(globals())

if __name__ == "__main__":
    import json
    out = flow.run()
    print(json.dumps(out, ensure_ascii=False, indent=2))
