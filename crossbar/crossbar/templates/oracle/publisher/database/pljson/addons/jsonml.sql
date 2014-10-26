CREATE OR REPLACE PACKAGE json_ml
AS
   /*
   Copyright (c) 2010 Jonas Krogsboell

   Permission is hereby granted, free of charge, to any person obtaining a copy
   of this software and associated documentation files (the "Software"), to deal
   in the Software without restriction, including without limitation the rights
   to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
   copies of the Software, and to permit persons to whom the Software is
   furnished to do so, subject to the following conditions:

   The above copyright notice and this permission notice shall be included in
   all copies or substantial portions of the Software.

   THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
   IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
   FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
   AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
   LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
   OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
   THE SOFTWARE.
   */

   /* This package contains extra methods to lookup types and
      an easy way of adding date values in json - without changing the structure */

   jsonml_stylesheet   XMLTYPE := NULL;

   FUNCTION xml2json (xml IN XMLTYPE)
      RETURN json_list;

   FUNCTION xmlstr2json (xmlstr IN VARCHAR2)
      RETURN json_list;
END json_ml;
/

CREATE OR REPLACE PACKAGE BODY json_ml
AS
   /*
   Copyright (c) 2010 Jonas Krogsboell

   Permission is hereby granted, free of charge, to any person obtaining a copy
   of this software and associated documentation files (the "Software"), to deal
   in the Software without restriction, including without limitation the rights
   to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
   copies of the Software, and to permit persons to whom the Software is
   furnished to do so, subject to the following conditions:

   The above copyright notice and this permission notice shall be included in
   all copies or substantial portions of the Software.

   THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
   IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
   FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
   AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
   LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
   OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
   THE SOFTWARE.
   */

   FUNCTION get_jsonml_stylesheet
      RETURN XMLTYPE;

   FUNCTION xml2json (xml IN XMLTYPE)
      RETURN json_list
   AS
      l_json          XMLTYPE;
      l_returnvalue   CLOB;
   BEGIN
      l_json          := xml.transform (get_jsonml_stylesheet);
      l_returnvalue   := l_json.getclobval ();
      l_returnvalue      :=
         DBMS_XMLGEN.CONVERT (l_returnvalue, DBMS_XMLGEN.entity_decode);
      --dbms_output.put_line(l_returnvalue);
      RETURN json_list (l_returnvalue);
   END xml2json;

   FUNCTION xmlstr2json (xmlstr IN VARCHAR2)
      RETURN json_list
   AS
   BEGIN
      RETURN xml2json (xmltype (xmlstr));
   END xmlstr2json;

   FUNCTION get_jsonml_stylesheet
      RETURN XMLTYPE
   AS
   BEGIN
      IF (jsonml_stylesheet IS NULL) THEN
         jsonml_stylesheet      :=
            xmltype (
               '<?xml version="1.0" encoding="UTF-8"?>
<!--
		JsonML.xslt

		Created: 2006-11-15-0551
		Modified: 2009-02-14-0927

		Released under an open-source license:
		http://jsonml.org/License.htm

		This transformation converts any XML document into JsonML.
		It omits processing-instructions and comment-nodes.

		To enable comment-nodes to be emitted as JavaScript comments,
		uncomment the Comment() template.
-->
<xsl:stylesheet version="1.0"
				xmlns:xsl="http://www.w3.org/1999/XSL/Transform">

	<xsl:output method="text"
				media-type="application/json"
				encoding="UTF-8"
				indent="no"
				omit-xml-declaration="yes" />

	<!-- constants -->
	<xsl:variable name="XHTML"
				  select="''http://www.w3.org/1999/xhtml''" />

	<xsl:variable name="START_ELEM"
				  select="''[''" />

	<xsl:variable name="END_ELEM"
				  select="'']''" />

	<xsl:variable name="VALUE_DELIM"
				  select="'',''" />

	<xsl:variable name="START_ATTRIB"
				  select="''{''" />

	<xsl:variable name="END_ATTRIB"
				  select="''}''" />

	<xsl:variable name="NAME_DELIM"
				  select="'':''" />

	<xsl:variable name="STRING_DELIM"
				  select="''&#x22;''" />

	<xsl:variable name="START_COMMENT"
				  select="''/*''" />

	<xsl:variable name="END_COMMENT"
				  select="''*/''" />

	<!-- root-node -->
	<xsl:template match="/">
		<xsl:apply-templates select="*" />
	</xsl:template>

	<!-- comments -->
	<xsl:template match="comment()">
	<!-- uncomment to support JSON comments -->
	<!--
		<xsl:value-of select="$START_COMMENT" />

		<xsl:value-of select="."
					  disable-output-escaping="yes" />

		<xsl:value-of select="$END_COMMENT" />
	-->
	</xsl:template>

	<!-- elements -->
	<xsl:template match="*">
		<xsl:value-of select="$START_ELEM" />

		<!-- tag-name string -->
		<xsl:value-of select="$STRING_DELIM" />
		<xsl:choose>
			<xsl:when test="namespace-uri()=$XHTML">
				<xsl:value-of select="local-name()" />
			</xsl:when>
			<xsl:otherwise>
				<xsl:value-of select="name()" />
			</xsl:otherwise>
		</xsl:choose>
		<xsl:value-of select="$STRING_DELIM" />

		<!-- attribute object -->
		<xsl:if test="count(@*)>0">
			<xsl:value-of select="$VALUE_DELIM" />
			<xsl:value-of select="$START_ATTRIB" />
			<xsl:for-each select="@*">
				<xsl:if test="position()>1">
					<xsl:value-of select="$VALUE_DELIM" />
				</xsl:if>
				<xsl:apply-templates select="." />
			</xsl:for-each>
			<xsl:value-of select="$END_ATTRIB" />
		</xsl:if>

		<!-- child elements and text-nodes -->
		<xsl:for-each select="*|text()">
			<xsl:value-of select="$VALUE_DELIM" />
			<xsl:apply-templates select="." />
		</xsl:for-each>

		<xsl:value-of select="$END_ELEM" />
	</xsl:template>

	<!-- text-nodes -->
	<xsl:template match="text()">
		<xsl:call-template name="escape-string">
			<xsl:with-param name="value"
							select="." />
		</xsl:call-template>
	</xsl:template>

	<!-- attributes -->
	<xsl:template match="@*">
		<xsl:value-of select="$STRING_DELIM" />
		<xsl:choose>
			<xsl:when test="namespace-uri()=$XHTML">
				<xsl:value-of select="local-name()" />
			</xsl:when>
			<xsl:otherwise>
				<xsl:value-of select="name()" />
			</xsl:otherwise>
		</xsl:choose>
		<xsl:value-of select="$STRING_DELIM" />

		<xsl:value-of select="$NAME_DELIM" />

		<xsl:call-template name="escape-string">
			<xsl:with-param name="value"
							select="." />
		</xsl:call-template>

	</xsl:template>

	<!-- escape-string: quotes and escapes -->
	<xsl:template name="escape-string">
		<xsl:param name="value" />

		<xsl:value-of select="$STRING_DELIM" />

		<xsl:if test="string-length($value)>0">
			<xsl:variable name="escaped-whacks">
				<!-- escape backslashes -->
				<xsl:call-template name="string-replace">
					<xsl:with-param name="value"
									select="$value" />
					<xsl:with-param name="find"
									select="''\''" />
					<xsl:with-param name="replace"
									select="''\\''" />
				</xsl:call-template>
			</xsl:variable>

			<xsl:variable name="escaped-LF">
				<!-- escape line feeds -->
				<xsl:call-template name="string-replace">
					<xsl:with-param name="value"
									select="$escaped-whacks" />
					<xsl:with-param name="find"
									select="''&#x0A;''" />
					<xsl:with-param name="replace"
									select="''\n''" />
				</xsl:call-template>
			</xsl:variable>

			<xsl:variable name="escaped-CR">
				<!-- escape carriage returns -->
				<xsl:call-template name="string-replace">
					<xsl:with-param name="value"
									select="$escaped-LF" />
					<xsl:with-param name="find"
									select="''&#x0D;''" />
					<xsl:with-param name="replace"
									select="''\r''" />
				</xsl:call-template>
			</xsl:variable>

			<xsl:variable name="escaped-tabs">
				<!-- escape tabs -->
				<xsl:call-template name="string-replace">
					<xsl:with-param name="value"
									select="$escaped-CR" />
					<xsl:with-param name="find"
									select="''&#x09;''" />
					<xsl:with-param name="replace"
									select="''\t''" />
				</xsl:call-template>
			</xsl:variable>

			<!-- escape quotes -->
			<xsl:call-template name="string-replace">
				<xsl:with-param name="value"
								select="$escaped-tabs" />
				<xsl:with-param name="find"
								select="''&quot;''" />
				<xsl:with-param name="replace"
								select="''\&quot;''" />
			</xsl:call-template>
		</xsl:if>

		<xsl:value-of select="$STRING_DELIM" />
	</xsl:template>

	<!-- string-replace: replaces occurances of one string with another -->
	<xsl:template name="string-replace">
		<xsl:param name="value" />
		<xsl:param name="find" />
		<xsl:param name="replace" />

		<xsl:choose>
			<xsl:when test="contains($value,$find)">
				<!-- replace and call recursively on next -->
				<xsl:value-of select="substring-before($value,$find)"
							  disable-output-escaping="yes" />
				<xsl:value-of select="$replace"
							  disable-output-escaping="yes" />
				<xsl:call-template name="string-replace">
					<xsl:with-param name="value"
									select="substring-after($value,$find)" />
					<xsl:with-param name="find"
									select="$find" />
					<xsl:with-param name="replace"
									select="$replace" />
				</xsl:call-template>
			</xsl:when>
			<xsl:otherwise>
				<!-- no replacement necessary -->
				<xsl:value-of select="$value"
							  disable-output-escaping="yes" />
			</xsl:otherwise>
		</xsl:choose>
	</xsl:template>

</xsl:stylesheet>');
      END IF;

      RETURN jsonml_stylesheet;
   END get_jsonml_stylesheet;
END json_ml;
/
