import xml.etree.ElementTree as ET
import os

def parse_archimate_model(xml_path):
    tree = ET.parse(xml_path)
    root = tree.getroot()

    # ArchiMate 3.0 namespace
    ns = {'archimate': 'http://www.opengroup.org/xsd/archimate/3.0/', 'xsi': 'http://www.w3.org/2001/XMLSchema-instance'}

    elements = {}
    for elem in root.findall('.//archimate:element', ns):
        elem_id = elem.get('identifier')
        elem_name_elem = elem.find('archimate:name', ns)
        elem_name = elem_name_elem.text if elem_name_elem is not None else "N/A"
        elem_type = elem.get(f'{{{ns["xsi"]}}}type')
        doc = elem.find('archimate:documentation', ns)
        elem_doc = doc.text if doc is not None else ""
        elements[elem_id] = {'id': elem_id, 'name': elem_name, 'type': elem_type, 'documentation': elem_doc}

    relationships = {}
    for rel in root.findall('.//archimate:relationship', ns):
        rel_id = rel.get('identifier')
        rel_type = rel.get(f'{{{ns["xsi"]}}}type')
        source = rel.get('source')
        target = rel.get('target')
        relationships[rel_id] = {'id': rel_id, 'type': rel_type, 'source': source, 'target': target}

    # Organizations (folders)
    organizations = []
    for item in root.findall('.//archimate:organizations/archimate:item', ns):
        label_elem = item.find('archimate:label', ns)
        label = label_elem.text if label_elem is not None else "Unnamed"
        for subitem in item.findall('.//archimate:item', ns):
            ref = subitem.get('identifierRef')
            if ref:
                organizations.append({'label': label, 'ref': ref})

    # Diagrams
    diagrams = []
    for diagram in root.findall('.//archimate:diagrams/archimate:view', ns):
        diagram_id = diagram.get('identifier')
        diagram_name_elem = diagram.find('archimate:name', ns)
        diagram_name = diagram_name_elem.text if diagram_name_elem is not None else "Unnamed Diagram"
        diagram_doc = diagram.find('archimate:documentation', ns)
        diagram_doc_text = diagram_doc.text if diagram_doc is not None else ""

        # Extract nodes and connections from the diagram
        nodes = []
        for node in diagram.findall('.//archimate:node', ns):
            node_id = node.get('identifier')
            ref = node.get('elementRef')
            x = int(node.get('x'))
            y = int(node.get('y'))
            w = int(node.get('w'))
            h = int(node.get('h'))
            # Extract style
            style = node.find('.//archimate:style', ns)
            fill_color = line_color = font_color = None
            if style is not None:
                fill = style.find('archimate:fillColor', ns)
                if fill is not None:
                    fill_color = f"rgb({fill.get('r')}, {fill.get('g')}, {fill.get('b')})"
                line = style.find('archimate:lineColor', ns)
                if line is not None:
                    line_color = f"rgb({line.get('r')}, {line.get('g')}, {line.get('b')})"
                font = style.find('archimate:font/archimate:color', ns)
                if font is not None:
                    font_color = f"rgb({font.get('r')}, {font.get('g')}, {font.get('b')})"

            nodes.append({
                'id': node_id,
                'elementRef': ref,
                'x': x,
                'y': y,
                'w': w,
                'h': h,
                'fill_color': fill_color,
                'line_color': line_color,
                'font_color': font_color
            })

        connections = []
        for conn in diagram.findall('.//archimate:connection', ns):
            conn_id = conn.get('identifier')
            rel_ref = conn.get('relationshipRef')
            source = conn.get('source')
            target = conn.get('target')

            # Extract bendpoint (for arrows)
            bendpoint = []
            for bp in conn.findall('.//archimate:bendpoint', ns):
                bendpoint.append({'x': int(bp.get('x')), 'y': int(bp.get('y'))})

            connections.append({
                'id': conn_id,
                'relationshipRef': rel_ref,
                'source': source,
                'target': target,
                'bendpoint': bendpoint
            })

        diagrams.append({
            'id': diagram_id,
            'name': diagram_name,
            'documentation': diagram_doc_text,
            'nodes': nodes,
            'connections': connections
        })

    return elements, relationships, organizations, diagrams

def generate_svg_diagram(diagram, elements):
    # Calculate canvas size based on nodes
    if not diagram['nodes']:
        width = 800
        height = 600
    else:
        max_x = max(n['x'] + n['w'] for n in diagram['nodes'])
        max_y = max(n['y'] + n['h'] for n in diagram['nodes'])
        width = max_x + 100
        height = max_y + 100

    svg_content = f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg" style="background-color:white; border:1px solid #ccc;">\n'

    # Draw connections first (so they appear under nodes)
    for conn in diagram['connections']:
        source_node = next((n for n in diagram['nodes'] if n['id'] == conn['source']), None)
        target_node = next((n for n in diagram['nodes'] if n['id'] == conn['target']), None)
        if not source_node or not target_node:
            continue

        sx = source_node['x'] + source_node['w'] // 2
        sy = source_node['y'] + source_node['h'] // 2
        tx = target_node['x'] + target_node['w'] // 2
        ty = target_node['y'] + target_node['h'] // 2

        points = [(sx, sy)]
        for bp in conn['bendpoint']:
            points.append((bp['x'], bp['y']))
        points.append((tx, ty))

        path = "M " + " L ".join([f"{x},{y}" for x, y in points])
        svg_content += f'<path d="{path}" stroke="black" fill="none" marker-end="url(#arrowhead)" stroke-width="1"/>\n'

    # Define arrowhead marker
    svg_content += '''
    <defs>
        <marker id="arrowhead" markerWidth="10" markerHeight="7"
                refX="10" refY="3.5" orient="auto">
            <polygon points="0 0, 10 3.5, 0 7" fill="black" />
        </marker>
    </defs>
    '''

    # Draw nodes
    for node in diagram['nodes']:
        ref = node['elementRef']
        elem = elements.get(ref, {'name': 'N/A'})
        name = elem['name']
        x, y, w, h = node['x'], node['y'], node['w'], node['h']
        fill = node['fill_color'] or 'lightgray'
        stroke = node['line_color'] or 'black'
        text_color = node['font_color'] or 'black'

        svg_content += f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" stroke="{stroke}" />\n'
        # Truncate text to fit inside box
        font_size = 12
        max_chars = w // 8  # Approximate char width
        display_name = name if len(name) <= max_chars else name[:max_chars - 3] + '...'
        svg_content += f'<text x="{x + w // 2}" y="{y + h // 2}" fill="{text_color}" font-size="{font_size}" text-anchor="middle" dominant-baseline="middle">{display_name}</text>\n'

    svg_content += '</svg>'
    return svg_content

def generate_html(elements, relationships, organizations, diagrams, output_path):
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>ArchiMate Model Export</title>
        <style>
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background-color: #f5f7fa; }
            .container { max-width: 1200px; margin: 0 auto; }
            h1 { color: #2c3e50; text-align: center; margin-bottom: 30px; }
            h2 { color: #3498db; border-bottom: 2px solid #3498db; padding-bottom: 8px; }
            .section { background-color: white; margin-bottom: 30px; padding: 20px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
            table { border-collapse: collapse; width: 100%; margin-bottom: 20px; }
            th, td { border: 1px solid #ddd; padding: 10px; text-align: left; }
            th { background-color: #eaf2f8; font-weight: bold; }
            .doc { white-space: pre-wrap; font-style: italic; color: #555; }
            .type-capability { background-color: #f9f2e7; }
            .type-resource { background-color: #f0f9f2; }
            .type-stakeholder { background-color: #e7f3f9; }
            .type-goal { background-color: #f9e7f3; }
            .type-relationship { background-color: #f0f0f0; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>ArchiMate Model Report</h1>
    """

    # Diagrams
    html_content += "<div class='section'><h2>Diagrams</h2><table><tr><th>ID</th><th>Name</th><th>Documentation</th></tr>"
    for d in diagrams:
        html_content += f"<tr><td>{d['id']}</td><td>{d['name']}</td><td class='doc'>{d['documentation']}</td></tr>"
    html_content += "</table></div>"

    # Organizations (Folders)
    html_content += "<div class='section'><h2>Organizations (Folders)</h2><table><tr><th>Label</th><th>Reference ID</th></tr>"
    for o in organizations:
        html_content += f"<tr><td>{o['label']}</td><td>{o['ref']}</td></tr>"
    html_content += "</table></div>"

    # Elements
    html_content += "<div class='section'><h2>Elements</h2><table><tr><th>ID</th><th>Name</th><th>Type</th><th>Documentation</th></tr>"
    for e in elements.values():
        cls = f"type-{e['type'].lower()}" if e['type'] else ''
        html_content += f"<tr class='{cls}'><td>{e['id']}</td><td>{e['name']}</td><td>{e['type']}</td><td class='doc'>{e['documentation']}</td></tr>"
    html_content += "</table></div>"

    # Relationships
    html_content += "<div class='section'><h2>Relationships</h2><table><tr><th>ID</th><th>Type</th><th>Source</th><th>Target</th></tr>"
    for r in relationships.values():
        html_content += f"<tr class='type-relationship'><td>{r['id']}</td><td>{r['type']}</td><td>{r['source']}</td><td>{r['target']}</td></tr>"
    html_content += "</table></div>"

    # Diagram Visualization (SVG inline)
    if diagrams:
        svg_code = generate_svg_diagram(diagrams[0], elements)
        html_content += f"<div class='section'><h2>Diagram Visualization</h2>{svg_code}</div>"

    html_content += """
        </div>
    </body>
    </html>
    """

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

def main():
    input_path = r"D:\(new model).xml"
    output_path = r"D:\archimate_model.html"
    
    elements, relationships, organizations, diagrams = parse_archimate_model(input_path)
    generate_html(elements, relationships, organizations, diagrams, output_path)
    print(f"HTML файл сохранён в: {output_path}")

if __name__ == "__main__":
    main()