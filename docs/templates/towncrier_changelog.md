{% for section, _ in sections|dictsort(by='key') %}
{% if section %}
# {{section}}

{% endif %}
{% if sections[section] %}
{% for category, val in definitions|dictsort if category in sections[section]%}

## {{ definitions[category]['name'] }}

{% if definitions[category]['showcontent'] %}
{% for text, values in sections[section][category]|dictsort(by='value') %}
* {% for value in values %}[{{value[1:]}}](https://github.com/crossbario/crossbar/issues/{{value[1:]}}){% endfor %}: {{ text }}
{% endfor %}
{% else %}
* {{ sections[section][category]['']|sort|join(', ') }}


{% endif %}
{% if sections[section][category]|length == 0 %}

*No significant changes.*


{% else %}
{% endif %}
{% endfor %}
{% else %}

*No significant changes.*


{% endif %}
{% endfor %}
