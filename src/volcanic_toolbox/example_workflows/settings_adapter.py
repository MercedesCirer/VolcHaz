import ast

def expression(template, value):
    if value is None:
        return ast.Constant(None)
    if isinstance(value, str) and any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=="Path" for n in ast.walk(template)):
        return ast.Call(func=ast.Name(id="Path",ctx=ast.Load()),args=[ast.Constant(value)],keywords=[])
    if isinstance(template,(ast.List,ast.Tuple)) and not template.elts:
        return ast.parse(repr(value),mode="eval").body
    if isinstance(template, ast.Call):
        keys={k.arg for k in template.keywords}
        keywords=[ast.keyword(arg=k.arg, value=expression(k.value, value[k.arg]) if k.arg in value else k.value) for k in template.keywords]
        keywords.extend(ast.keyword(arg=key, value=ast.parse(repr(item), mode="eval").body)
                        for key,item in value.items() if key not in keys)
        return ast.Call(func=template.func, args=template.args, keywords=keywords)
    if isinstance(template, (ast.List, ast.Tuple)):
        return type(template)(elts=[expression(template.elts[min(i, len(template.elts) - 1)], v) for i, v in enumerate(value)], ctx=ast.Load())
    if isinstance(template, ast.Dict):
        original = {ast.literal_eval(k): v for k, v in zip(template.keys, template.values)}
        return ast.Dict(keys=[ast.Constant(k) for k in value], values=[expression(original[k], v) if k in original else ast.parse(repr(v), mode='eval').body for k, v in value.items()])
    return ast.parse(repr(value), mode='eval').body
