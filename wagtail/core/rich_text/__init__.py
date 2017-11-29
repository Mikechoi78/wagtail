from django.utils.functional import cached_property
from django.utils.safestring import mark_safe

from wagtail.core import hooks
from wagtail.core.rich_text.feature_registry import FeatureRegistry
from wagtail.core.rich_text.pages import PageLinkHandler
from wagtail.core.rich_text.rewriters import EmbedRewriter, LinkRewriter, MultiRuleRewriter
from wagtail.core.whitelist import allow_without_attributes, Whitelister, DEFAULT_ELEMENT_RULES


features = FeatureRegistry()


class DbWhitelister(Whitelister):
    """
    A custom whitelisting engine to convert the HTML as returned by the rich text editor
    into the pseudo-HTML format stored in the database (in which images, documents and other
    linked objects are identified by ID rather than URL):

    * implements a 'construct_whitelister_element_rules' hook so that other apps can modify
      the whitelist ruleset (e.g. to permit additional HTML elements beyond those in the base
      Whitelister module);
    * replaces any element with a 'data-embedtype' attribute with an <embed> element, with
      attributes supplied by the handler for that type as defined in embed_handlers;
    * rewrites the attributes of any <a> element with a 'data-linktype' attribute, as
      determined by the handler for that type defined in link_handlers, while keeping the
      element content intact.
    """
    def __init__(self, features=None):
        self.features = features

    @cached_property
    def element_rules(self):
        if self.features is None:
            # use the legacy construct_whitelister_element_rules hook to build up whitelist rules
            element_rules = DEFAULT_ELEMENT_RULES.copy()
            for fn in hooks.get_hooks('construct_whitelister_element_rules'):
                element_rules.update(fn())
        else:
            # use the feature registry to build up whitelist rules
            element_rules = {
                '[document]': allow_without_attributes,
                'p': allow_without_attributes,
                'div': allow_without_attributes,
                'br': allow_without_attributes,
            }
            for feature_name in self.features:
                element_rules.update(features.get_whitelister_element_rules(feature_name))

        return element_rules

    @cached_property
    def embed_handlers(self):
        embed_handlers = {}
        for hook in hooks.get_hooks('register_rich_text_embed_handler'):
            handler_name, handler = hook()
            embed_handlers[handler_name] = handler

        return embed_handlers

    @cached_property
    def link_handlers(self):
        link_handlers = {
            'page': PageLinkHandler,
        }
        for hook in hooks.get_hooks('register_rich_text_link_handler'):
            handler_name, handler = hook()
            link_handlers[handler_name] = handler

        return link_handlers

    def clean_tag_node(self, doc, tag):
        if 'data-embedtype' in tag.attrs:
            embed_type = tag['data-embedtype']
            # fetch the appropriate embed handler for this embedtype
            embed_handler = self.embed_handlers[embed_type]
            embed_attrs = embed_handler.get_db_attributes(tag)
            embed_attrs['embedtype'] = embed_type

            embed_tag = doc.new_tag('embed', **embed_attrs)
            embed_tag.can_be_empty_element = True
            tag.replace_with(embed_tag)
        elif tag.name == 'a' and 'data-linktype' in tag.attrs:
            # first, whitelist the contents of this tag
            for child in tag.contents:
                self.clean_node(doc, child)

            link_type = tag['data-linktype']
            link_handler = self.link_handlers[link_type]
            link_attrs = link_handler.get_db_attributes(tag)
            link_attrs['linktype'] = link_type
            tag.attrs.clear()
            tag.attrs.update(**link_attrs)
        else:
            if tag.name == 'div':
                tag.name = 'p'

            super(DbWhitelister, self).clean_tag_node(doc, tag)


# Rewriter functions to be built up on first call to expand_db_html, using the utility classes
# from wagtail.core.rich_text.rewriters along with the register_rich_text_embed_handler /
# register_rich_text_link_handler hooks

FRONTEND_REWRITER = None
EDITOR_REWRITER = None


def expand_db_html(html, for_editor=False):
    """
    Expand database-representation HTML into proper HTML usable in either
    templates or the rich text editor
    """
    global FRONTEND_REWRITER, EDITOR_REWRITER

    if for_editor:

        if EDITOR_REWRITER is None:
            embed_rules = {}
            for hook in hooks.get_hooks('register_rich_text_embed_handler'):
                handler_name, handler = hook()
                embed_rules[handler_name] = handler.expand_db_attributes_for_editor

            link_rules = {}
            for hook in hooks.get_hooks('register_rich_text_link_handler'):
                handler_name, handler = hook()
                link_rules[handler_name] = handler.expand_db_attributes_for_editor

            EDITOR_REWRITER = MultiRuleRewriter([
                LinkRewriter(link_rules), EmbedRewriter(embed_rules)
            ])

        return EDITOR_REWRITER(html)

    else:

        if FRONTEND_REWRITER is None:
            embed_rules = {}
            for hook in hooks.get_hooks('register_rich_text_embed_handler'):
                handler_name, handler = hook()
                embed_rules[handler_name] = handler.expand_db_attributes

            link_rules = {}
            for hook in hooks.get_hooks('register_rich_text_link_handler'):
                handler_name, handler = hook()
                link_rules[handler_name] = handler.expand_db_attributes

            FRONTEND_REWRITER = MultiRuleRewriter([
                LinkRewriter(link_rules), EmbedRewriter(embed_rules)
            ])

        return FRONTEND_REWRITER(html)


class RichText:
    """
    A custom object used to represent a renderable rich text value.
    Provides a 'source' property to access the original source code,
    and renders to the front-end HTML rendering.
    Used as the native value of a wagtailcore.blocks.field_block.RichTextBlock.
    """
    def __init__(self, source):
        self.source = (source or '')

    def __html__(self):
        return '<div class="rich-text">' + expand_db_html(self.source) + '</div>'

    def __str__(self):
        return mark_safe(self.__html__())

    def __bool__(self):
        return bool(self.source)
    __nonzero__ = __bool__
