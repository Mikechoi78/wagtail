from urllib.parse import urlencode

from django.db import transaction
from django.shortcuts import get_list_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext

from wagtail.admin import messages
from wagtail.admin.views.pages.utils import get_valid_next_url_from_request
from wagtail.core import hooks
from wagtail.core.models import Page, UserPagePermissionsProxy


def unpublish(request, parent_page_id):
    next_url = get_valid_next_url_from_request(request)
    if not next_url:
        next_url = reverse('wagtailadmin_explore', args=[parent_page_id])

    page_ids = list(map(int, request.GET.getlist('id')))
    user_perms = UserPagePermissionsProxy(request.user)
    pages = []
    pages_with_no_access = []

    for page in get_list_or_404(Page, id__in=page_ids):
        page = page.specific
        if not user_perms.for_page(page).can_unpublish():
            pages_with_no_access.append(page)
        else:
            pages.append(page)

    if request.method == 'GET':
        _pages = []
        for page in pages:
            _pages.append({
                'page': page,
                'live_descendant_count': page.get_descendants().live().count(),
            })

        return TemplateResponse(request, 'wagtailadmin/pages/bulk_actions/confirm_bulk_unpublish.html', {
            'pages': _pages,
            'pages_with_no_access': pages_with_no_access,
            'next': next_url,
            'submit_url': (
                reverse('wagtailadmin_bulk_unpublish', args=[parent_page_id])
                + '?' + urlencode([('id', page_id) for page_id in page_ids])
            ),
            'has_live_descendants': any(map(lambda x: x['live_descendant_count'] > 0, _pages)),
        })
    elif request.method == 'POST':
        num_parent_pages = 0
        include_descendants = request.POST.get("include_descendants", False)
        if include_descendants:
            num_child_pages = 0
        with transaction.atomic():
            for page in pages:
                for fn in hooks.get_hooks('before_unpublish_page'):
                    result = fn(request, page)
                    if hasattr(result, 'status_code'):
                        return result

                page.unpublish(user=request.user)
                num_parent_pages += 1

                if include_descendants:
                    for live_descendant_page in page.get_descendants().live().defer_streamfields().specific():
                        if user_perms.for_page(live_descendant_page).can_unpublish():
                            live_descendant_page.unpublish()
                            num_child_pages += 1

                for fn in hooks.get_hooks('after_unpublish_page'):
                    result = fn(request, page)
                    if hasattr(result, 'status_code'):
                        return result

        if num_parent_pages == 1:
            if include_descendants:
                if num_child_pages == 0:
                    success_message = _("1 page has been unpublished")
                else:
                    success_message = ngettext(
                        "1 page and %(num_child_pages)d child page have been unpublished",
                        "1 page and %(num_child_pages)d child pages have been unpublished",
                        num_child_pages
                    ) % {
                        'num_child_pages': num_child_pages
                    }
            else:
                success_message = _("1 page has been unpublished")
        else:
            if include_descendants:
                if num_child_pages == 0:
                    success_message = _("%(num_parent_pages)d pages have been unpublished") % {'num_parent_pages': num_parent_pages}
                else:
                    success_message = ngettext(
                        "%(num_parent_pages)d pages and %(num_child_pages)d child page have been unpublished",
                        "%(num_parent_pages)d pages and %(num_child_pages)d child pages have been unpublished",
                        num_child_pages
                    ) % {
                        'num_child_pages': num_child_pages,
                        'num_parent_pages': num_parent_pages
                    }
            else:
                success_message = _("%(num_parent_pages)d pages have been unpublished") % {'num_parent_pages': num_parent_pages}

        messages.success(request, success_message)
    return redirect(next_url)
