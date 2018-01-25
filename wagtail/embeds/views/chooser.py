import json

from django.forms.utils import ErrorList
from django.utils.translation import ugettext as _

from wagtail.admin.modal_workflow import render_modal_workflow
from wagtail.embeds import embeds
from wagtail.embeds.exceptions import EmbedNotFoundException, EmbedUnsupportedProviderException
from wagtail.embeds.finders.embedly import AccessDeniedEmbedlyException, EmbedlyException
from wagtail.embeds.format import embed_to_editor_html
from wagtail.embeds.forms import EmbedForm


def chooser(request):
    form = EmbedForm(initial=request.GET.dict())

    return render_modal_workflow(request, 'wagtailembeds/chooser/chooser.html', 'wagtailembeds/chooser/chooser.js', {
        'form': form,
    })


def chooser_upload(request):
    if request.method == 'POST':
        form = EmbedForm(request.POST, request.FILES)

        if form.is_valid():
            error = None
            try:
                embed_html = embed_to_editor_html(form.cleaned_data['url'])
                embed_obj = embeds.get_embed(form.cleaned_data['url'])
                embed_json = json.dumps({
                    'embedType': embed_obj.type,
                    'url': embed_obj.url,
                    'providerName': embed_obj.provider_name,
                    'authorName': embed_obj.author_name,
                    'thumbnail': embed_obj.thumbnail_url,
                    'title': embed_obj.title,
                })
                return render_modal_workflow(
                    request, None, 'wagtailembeds/chooser/embed_chosen.js',
                    {'embed_html': embed_html, 'embed_json': embed_json}
                )
            except AccessDeniedEmbedlyException:
                error = _("There seems to be a problem with your embedly API key. Please check your settings.")
            except (EmbedNotFoundException, EmbedUnsupportedProviderException):
                error = _("Cannot find an embed for this URL.")
            except EmbedlyException:
                error = _(
                    "There seems to be an error with Embedly while trying to embed this URL."
                    " Please try again later."
                )

            if error:
                errors = form._errors.setdefault('url', ErrorList())
                errors.append(error)
                return render_modal_workflow(
                    request,
                    'wagtailembeds/chooser/chooser.html',
                    'wagtailembeds/chooser/chooser.js',
                    {
                        'form': form,
                    }
                )
    else:
        form = EmbedForm()

    return render_modal_workflow(request, 'wagtailembeds/chooser/chooser.html', 'wagtailembeds/chooser/chooser.js', {
        'form': form,
    })
