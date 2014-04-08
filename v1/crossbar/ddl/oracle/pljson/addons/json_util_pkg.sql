SET DEFINE OFF;

CREATE OR REPLACE PACKAGE json_util_pkg
   AUTHID CURRENT_USER
AS
   /*

   Purpose:    JSON utilities for PL/SQL
   see http://ora-00001.blogspot.com/

   Remarks:

   Who     Date        Description
   ------  ----------  -------------------------------------
   MBR     30.01.2010  Created
   JKR     01.05.2010  Edited to fit in PL/JSON
   JKR     19.01.2011  Newest stylesheet + bugfix handling

   */

   -- generate JSON from REF Cursor
   FUNCTION ref_cursor_to_json (p_ref_cursor   IN SYS_REFCURSOR,
                                p_max_rows     IN NUMBER := NULL,
                                p_skip_rows    IN NUMBER := NULL)
      RETURN json_list;

   -- generate JSON from SQL statement
   FUNCTION sql_to_json (p_sql         IN VARCHAR2,
                         p_max_rows    IN NUMBER := NULL,
                         p_skip_rows   IN NUMBER := NULL)
      RETURN json_list;
END json_util_pkg;
/

CREATE OR REPLACE PACKAGE BODY json_util_pkg
AS
   scanner_exception             EXCEPTION;
   PRAGMA EXCEPTION_INIT (scanner_exception, -20100);
   parser_exception              EXCEPTION;
   PRAGMA EXCEPTION_INIT (parser_exception, -20101);

   /*

   Purpose:    JSON utilities for PL/SQL

   Remarks:

   Who     Date        Description
   ------  ----------  -------------------------------------
   MBR     30.01.2010  Created

   */


   g_json_null_object   CONSTANT VARCHAR2 (20) := '{ }';


   FUNCTION get_xml_to_json_stylesheet
      RETURN VARCHAR2
   AS
   BEGIN
      /*

      Purpose:    return XSLT stylesheet for XML to JSON transformation

      Remarks:    see http://code.google.com/p/xml2json-xslt/

      Who     Date        Description
      ------  ----------  -------------------------------------
      MBR     30.01.2010  Created
      MBR     30.01.2010  Added fix for nulls

      */


      RETURN q'^<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
<!--
  Copyright (c) 2006,2008 Doeke Zanstra
  All rights reserved.

  Redistribution and use in source and binary forms, with or without modification,
  are permitted provided that the following conditions are met:

  Redistributions of source code must retain the above copyright notice, this
  list of conditions and the following disclaimer. Redistributions in binary
  form must reproduce the above copyright notice, this list of conditions and the
  following disclaimer in the documentation and/or other materials provided with
  the distribution.

  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
  ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
  WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
  IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT,
  INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
  BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
  DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
  LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR
  OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF
  THE POSSIBILITY OF SUCH DAMAGE.
-->

  <xsl:output indent="no" omit-xml-declaration="yes" method="text" encoding="UTF-8" media-type="text/x-json"/>
        <xsl:strip-space elements="*"/>
  <!--contant-->
  <xsl:variable name="d">0123456789</xsl:variable>

  <!-- ignore document text -->
  <xsl:template match="text()[preceding-sibling::node() or following-sibling::node()]"/>

  <!-- string -->
  <xsl:template match="text()">
    <xsl:call-template name="escape-string">
      <xsl:with-param name="s" select="."/>
    </xsl:call-template>
  </xsl:template>

  <!-- Main template for escaping strings; used by above template and for object-properties
       Responsibilities: placed quotes around string, and chain up to next filter, escape-bs-string -->
  <xsl:template name="escape-string">
    <xsl:param name="s"/>
    <xsl:text>"</xsl:text>
    <xsl:call-template name="escape-bs-string">
      <xsl:with-param name="s" select="$s"/>
    </xsl:call-template>
    <xsl:text>"</xsl:text>
  </xsl:template>

  <!-- Escape the backslash (\) before everything else. -->
  <xsl:template name="escape-bs-string">
    <xsl:param name="s"/>
    <xsl:choose>
      <xsl:when test="contains($s,'\')">
        <xsl:call-template name="escape-quot-string">
          <xsl:with-param name="s" select="concat(substring-before($s,'\'),'\\')"/>
        </xsl:call-template>
        <xsl:call-template name="escape-bs-string">
          <xsl:with-param name="s" select="substring-after($s,'\')"/>
        </xsl:call-template>
      </xsl:when>
      <xsl:otherwise>
        <xsl:call-template name="escape-quot-string">
          <xsl:with-param name="s" select="$s"/>
        </xsl:call-template>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>

  <!-- Escape the double quote ("). -->
  <xsl:template name="escape-quot-string">
    <xsl:param name="s"/>
    <xsl:choose>
      <xsl:when test="contains($s,'&quot;')">
        <xsl:call-template name="encode-string">
          <xsl:with-param name="s" select="concat(substring-before($s,'&quot;'),'\&quot;')"/>
        </xsl:call-template>
        <xsl:call-template name="escape-quot-string">
          <xsl:with-param name="s" select="substring-after($s,'&quot;')"/>
        </xsl:call-template>
      </xsl:when>
      <xsl:otherwise>
        <xsl:call-template name="encode-string">
          <xsl:with-param name="s" select="$s"/>
        </xsl:call-template>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>

  <!-- Replace tab, line feed and/or carriage return by its matching escape code. Can't escape backslash
       or double quote here, because they don't replace characters (&#x0; becomes \t), but they prefix
       characters (\ becomes \\). Besides, backslash should be seperate anyway, because it should be
       processed first. This function can't do that. -->
  <xsl:template name="encode-string">
    <xsl:param name="s"/>
    <xsl:choose>
      <!-- tab -->
      <xsl:when test="contains($s,'&#x9;')">
        <xsl:call-template name="encode-string">
          <xsl:with-param name="s" select="concat(substring-before($s,'&#x9;'),'\t',substring-after($s,'&#x9;'))"/>
        </xsl:call-template>
      </xsl:when>
      <!-- line feed -->
      <xsl:when test="contains($s,'&#xA;')">
        <xsl:call-template name="encode-string">
          <xsl:with-param name="s" select="concat(substring-before($s,'&#xA;'),'\n',substring-after($s,'&#xA;'))"/>
        </xsl:call-template>
      </xsl:when>
      <!-- carriage return -->
      <xsl:when test="contains($s,'&#xD;')">
        <xsl:call-template name="encode-string">
          <xsl:with-param name="s" select="concat(substring-before($s,'&#xD;'),'\r',substring-after($s,'&#xD;'))"/>
        </xsl:call-template>
      </xsl:when>
      <xsl:otherwise><xsl:value-of select="$s"/></xsl:otherwise>
    </xsl:choose>
  </xsl:template>

  <!-- number (no support for javascript mantissa) -->
  <xsl:template match="text()[not(string(number())='NaN' or
                      (starts-with(.,'0' ) and . != '0' and
not(starts-with(.,'0.' ))) or
                      (starts-with(.,'-0' ) and . != '-0' and
not(starts-with(.,'-0.' )))
                      )]">
    <xsl:value-of select="."/>
  </xsl:template>

  <!-- boolean, case-insensitive -->
  <xsl:template match="text()[translate(.,'TRUE','true')='true']">true</xsl:template>
  <xsl:template match="text()[translate(.,'FALSE','false')='false']">false</xsl:template>

  <!-- object -->
  <xsl:template match="*" name="base">
    <xsl:if test="not(preceding-sibling::*)">{</xsl:if>
    <xsl:call-template name="escape-string">
      <xsl:with-param name="s" select="name()"/>
    </xsl:call-template>
    <xsl:text>:</xsl:text>
    <!-- check type of node -->
    <xsl:choose>
      <!-- null nodes -->
      <xsl:when test="count(child::node())=0">null</xsl:when>
      <!-- other nodes -->
      <xsl:otherwise>
        <xsl:apply-templates select="child::node()"/>
      </xsl:otherwise>
    </xsl:choose>
    <!-- end of type check -->
    <xsl:if test="following-sibling::*">,</xsl:if>
    <xsl:if test="not(following-sibling::*)">}</xsl:if>
  </xsl:template>

  <!-- array -->
  <xsl:template match="*[count(../*[name(../*)=name(.)])=count(../*) and count(../*)&gt;1]">
    <xsl:if test="not(preceding-sibling::*)">[</xsl:if>
    <xsl:choose>
      <xsl:when test="not(child::node())">
        <xsl:text>null</xsl:text>
      </xsl:when>
      <xsl:otherwise>
        <xsl:apply-templates select="child::node()"/>
      </xsl:otherwise>
    </xsl:choose>
    <xsl:if test="following-sibling::*">,</xsl:if>
    <xsl:if test="not(following-sibling::*)">]</xsl:if>
  </xsl:template>

  <!-- convert root element to an anonymous container -->
  <xsl:template match="/">
    <xsl:apply-templates select="node()"/>
  </xsl:template>

</xsl:stylesheet>^';
   END get_xml_to_json_stylesheet;


   FUNCTION ref_cursor_to_json (p_ref_cursor   IN SYS_REFCURSOR,
                                p_max_rows     IN NUMBER := NULL,
                                p_skip_rows    IN NUMBER := NULL)
      RETURN json_list
   AS
      l_ctx           DBMS_XMLGEN.ctxhandle;
      l_num_rows      PLS_INTEGER;
      l_xml           XMLTYPE;
      l_json          XMLTYPE;
      l_returnvalue   CLOB;
   BEGIN
      /*

      Purpose:    generate JSON from REF Cursor

      Remarks:

      Who     Date        Description
      ------  ----------  -------------------------------------
      MBR     30.01.2010  Created
      JKR     01.05.2010  Edited to fit in PL/JSON

      */

      l_ctx        := DBMS_XMLGEN.newcontext (p_ref_cursor);

      DBMS_XMLGEN.setnullhandling (l_ctx, DBMS_XMLGEN.empty_tag);

      -- for pagination

      IF p_max_rows IS NOT NULL THEN
         DBMS_XMLGEN.setmaxrows (l_ctx, p_max_rows);
      END IF;

      IF p_skip_rows IS NOT NULL THEN
         DBMS_XMLGEN.setskiprows (l_ctx, p_skip_rows);
      END IF;

      -- get the XML content
      l_xml        := DBMS_XMLGEN.getxmltype (l_ctx, DBMS_XMLGEN.none);

      l_num_rows   := DBMS_XMLGEN.getnumrowsprocessed (l_ctx);

      DBMS_XMLGEN.closecontext (l_ctx);

      CLOSE p_ref_cursor;

      IF l_num_rows > 0 THEN
         -- perform the XSL transformation
         l_json          := l_xml.transform (xmltype (get_xml_to_json_stylesheet));
         l_returnvalue   := l_json.getclobval ();
      ELSE
         l_returnvalue   := g_json_null_object;
      END IF;

      l_returnvalue      :=
         DBMS_XMLGEN.CONVERT (l_returnvalue, DBMS_XMLGEN.entity_decode);

      IF (l_num_rows = 0) THEN
         RETURN json_list ();
      ELSE
         IF (l_num_rows = 1) THEN
            DECLARE
               ret   json_list := json_list ();
            BEGIN
               ret.append (
                  json (json (l_returnvalue).get ('ROWSET')).get ('ROW'));
               RETURN ret;
            END;
         ELSE
            RETURN json_list (json (l_returnvalue).get ('ROWSET'));
         END IF;
      END IF;
   EXCEPTION
      WHEN scanner_exception THEN
         DBMS_OUTPUT.put ('Scanner problem with the following input: ');
         DBMS_OUTPUT.put_line (l_returnvalue);
         RAISE;
      WHEN parser_exception THEN
         DBMS_OUTPUT.put ('Parser problem with the following input: ');
         DBMS_OUTPUT.put_line (l_returnvalue);
         RAISE;
      WHEN OTHERS THEN
         RAISE;
   END ref_cursor_to_json;

   FUNCTION sql_to_json (p_sql         IN VARCHAR2,
                         p_max_rows    IN NUMBER := NULL,
                         p_skip_rows   IN NUMBER := NULL)
      RETURN json_list
   AS
      v_cur   SYS_REFCURSOR;
   BEGIN
      OPEN v_cur FOR p_sql;

      RETURN ref_cursor_to_json (v_cur, p_max_rows, p_skip_rows);
   END sql_to_json;
END json_util_pkg;
/
