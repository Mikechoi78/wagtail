from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.utils.translation import ugettext as _

from wagtail.wagtailcore.models import Site
from wagtail.wagtailsites.forms import SiteForm


@permission_required('site.change_site')
def index(request):
    sites = Site.objects.all()
    return render(request, 'wagtailsites/index.html', {
        'sites': sites,
    })


@permission_required('site.add_site')
def create(request):
    if request.POST:
        form = SiteForm(request.POST)
        if form.is_valid():
            site = form.save()
            messages.success(request, _("Site '{0}' created.").format(site.hostname))
            return redirect('wagtailsites_index')
        else:
            messages.error(request, _("The site could not be created due to errors."))
    else:
        form = SiteForm()

    return render(request, 'wagtailsites/create.html', {
        'form': form,
    })


@permission_required('site.change_site')
def edit(request, site_id):
    site = get_object_or_404(Site, id=site_id)

    if request.POST:
        form = SiteForm(request.POST, instance=site)
        if form.is_valid():
            site = form.save()
            messages.success(request, _("Site '{0}' updated.").format(site.hostname))
            return redirect('wagtailsites_index')
        else:
            messages.error(request, _("The site could not be saved due to errors."))
    else:
        form = SiteForm(instance=site)

    return render(request, 'wagtailsites/edit.html', {
        'site': site,
        'form': form,
    })
