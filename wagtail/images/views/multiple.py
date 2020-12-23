import os.path

from django.core.exceptions import PermissionDenied
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.vary import vary_on_headers
from django.views.generic.base import TemplateView, View

from wagtail.admin.views.generic import PermissionCheckedMixin
from wagtail.images import get_image_model
from wagtail.images.fields import ALLOWED_EXTENSIONS
from wagtail.images.forms import get_image_form, get_image_multi_form
from wagtail.images.models import UploadedImage
from wagtail.images.permissions import permission_policy
from wagtail.search.backends import get_search_backends


class AddView(PermissionCheckedMixin, TemplateView):
    permission_policy = permission_policy
    permission_required = 'add'
    template_name = 'wagtailimages/multiple/add.html'
    edit_form_template_name = 'wagtailimages/multiple/edit_form.html'
    upload_model = UploadedImage

    def get_model(self):
        return get_image_model()

    def get_upload_form_class(self):
        return get_image_form(self.model)

    def get_edit_form_class(self):
        return get_image_multi_form(self.model)

    @method_decorator(vary_on_headers('X-Requested-With'))
    def dispatch(self, request):
        self.model = self.get_model()

        return super().dispatch(request)

    def save_object(self, form):
        image = form.save(commit=False)
        image.uploaded_by_user = self.request.user
        image.file_size = image.file.size
        image.file.seek(0)
        image._set_file_hash(image.file.read())
        image.file.seek(0)
        image.save()
        return image

    def get_edit_object_form_context_data(self):
        """
        Return the context data necessary for rendering the HTML form for editing
        an image that has been successfully uploaded
        """
        edit_form_class = self.get_edit_form_class()
        return {
            'image': self.object,
            'edit_action': reverse('wagtailimages:edit_multiple', args=(self.object.id,)),
            'delete_action': reverse('wagtailimages:delete_multiple', args=(self.object.id,)),
            'form': edit_form_class(
                instance=self.object, prefix='image-%d' % self.object.id, user=self.request.user
            ),
        }

    def get_edit_object_response_data(self):
        """
        Return the JSON response data for an image that has been successfully uploaded
        """
        return {
            'success': True,
            'image_id': int(self.object.id),
            'form': render_to_string(
                self.edit_form_template_name,
                self.get_edit_object_form_context_data(),
                request=self.request
            ),
        }

    def get_invalid_response_data(self, form):
        """
        Return the JSON response data for an invalid form submission
        """
        return {
            'success': False,
            'error_message': '\n'.join(form.errors['file']),
        }

    def get_edit_upload_form_context_data(self):
        """
        Return the context data necessary for rendering the HTML form for supplying the
        metadata to turn an UploadedImage into a final image
        """
        edit_form_class = self.get_edit_form_class()
        return {
            'uploaded_image': self.upload_object,
            'edit_action': reverse('wagtailimages:create_multiple_from_uploaded_image', args=(self.upload_object.id,)),
            'delete_action': reverse('wagtailimages:delete_upload_multiple', args=(self.upload_object.id,)),
            'form': edit_form_class(
                instance=self.object, prefix='uploaded-image-%d' % self.upload_object.id, user=self.request.user
            ),
        }

    def get_edit_upload_response_data(self):
        """
        Return the JSON response data for an image that has been uploaded to an
        UploadedImage and now needs extra metadata to become a final image
        """
        return {
            'success': True,
            'uploaded_image_id': self.upload_object.id,
            'form': render_to_string(
                self.edit_form_template_name,
                self.get_edit_upload_form_context_data(),
                request=self.request
            ),
        }

    def post(self, request):
        if not request.is_ajax():
            return HttpResponseBadRequest("Cannot POST to this view without AJAX")

        if not request.FILES:
            return HttpResponseBadRequest("Must upload a file")

        # Build a form for validation
        self.upload_form_class = self.get_upload_form_class()
        form = self.upload_form_class({
            'title': request.FILES['files[]'].name,
            'collection': request.POST.get('collection'),
        }, {
            'file': request.FILES['files[]'],
        }, user=request.user)

        if form.is_valid():
            # Save it
            self.object = self.save_object(form)

            # Success! Send back an edit form for this image to the user
            return JsonResponse(self.get_edit_object_response_data())
        elif 'file' in form.errors:
            # The uploaded file is invalid; reject it now
            return JsonResponse(self.get_invalid_response_data(form))
        else:
            # Some other field of the image form has failed validation, e.g. a required metadata field
            # on a custom image model. Store the image as an UploadedImage instead and present the
            # edit form so that it will become a proper Image when successfully filled in
            self.upload_object = self.upload_model.objects.create(
                file=self.request.FILES['files[]'], uploaded_by_user=self.request.user
            )
            self.object = self.model(
                title=self.request.FILES['files[]'].name,
                collection_id=self.request.POST.get('collection')
            )

            return JsonResponse(self.get_edit_upload_response_data())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Instantiate a dummy copy of the form that we can retrieve validation messages and media from;
        # actual rendering of forms will happen on AJAX POST rather than here
        self.upload_form_class = self.get_upload_form_class()
        form = self.upload_form_class(user=self.request.user)

        collections = self.permission_policy.collections_user_has_permission_for(self.request.user, 'add')
        if len(collections) < 2:
            # no need to show a collections chooser
            collections = None

        context.update({
            'max_filesize': form.fields['file'].max_upload_size,
            'help_text': form.fields['file'].help_text,
            'allowed_extensions': ALLOWED_EXTENSIONS,
            'error_max_file_size': form.fields['file'].error_messages['file_too_large_unknown_size'],
            'error_accepted_file_types': form.fields['file'].error_messages['invalid_image_extension'],
            'collections': collections,
            'form_media': form.media,
        })

        return context


class EditView(View):
    http_method_names = ['post']
    permission_policy = permission_policy

    def get_model(self):
        return get_image_model()

    def get_edit_form_class(self):
        return get_image_multi_form(self.model)

    def post(self, request, image_id, callback=None):
        self.model = self.get_model()
        self.form_class = self.get_edit_form_class()

        image = get_object_or_404(self.model, id=image_id)

        if not request.is_ajax():
            return HttpResponseBadRequest("Cannot POST to this view without AJAX")

        if not self.permission_policy.user_has_permission_for_instance(request.user, 'change', image):
            raise PermissionDenied

        form = self.form_class(
            request.POST, request.FILES, instance=image, prefix='image-%d' % image_id, user=request.user
        )

        if form.is_valid():
            form.save()

            # Reindex the image to make sure all tags are indexed
            for backend in get_search_backends():
                backend.add(image)

            return JsonResponse({
                'success': True,
                'image_id': int(image_id),
            })
        else:
            return JsonResponse({
                'success': False,
                'image_id': int(image_id),
                'form': render_to_string('wagtailimages/multiple/edit_form.html', {
                    'image': image,
                    'edit_action': reverse('wagtailimages:edit_multiple', args=(image_id,)),
                    'delete_action': reverse('wagtailimages:delete_multiple', args=(image_id,)),
                    'form': form,
                }, request=request),
            })


class DeleteView(View):
    http_method_names = ['post']
    permission_policy = permission_policy

    def get_model(self):
        return get_image_model()

    def post(self, request, image_id):
        self.model = self.get_model()
        image = get_object_or_404(self.model, id=image_id)

        if not request.is_ajax():
            return HttpResponseBadRequest("Cannot POST to this view without AJAX")

        if not self.permission_policy.user_has_permission_for_instance(request.user, 'delete', image):
            raise PermissionDenied

        image.delete()

        return JsonResponse({
            'success': True,
            'image_id': int(image_id),
        })


class CreateFromUploadedImageView(View):
    http_method_names = ['post']

    def get_model(self):
        return get_image_model()

    def get_edit_form_class(self):
        return get_image_multi_form(self.model)

    def post(self, request, uploaded_image_id):
        self.model = self.get_model()
        self.form_class = self.get_edit_form_class()

        uploaded_image = get_object_or_404(UploadedImage, id=uploaded_image_id)

        if not request.is_ajax():
            return HttpResponseBadRequest("Cannot POST to this view without AJAX")

        if uploaded_image.uploaded_by_user != request.user:
            raise PermissionDenied

        image = self.model()
        form = self.form_class(
            request.POST, request.FILES, instance=image, prefix='uploaded-image-%d' % uploaded_image_id, user=request.user
        )

        if form.is_valid():
            # assign the file content from uploaded_image to the image object, to ensure it gets saved to
            # Image's storage

            image.file.save(os.path.basename(uploaded_image.file.name), uploaded_image.file.file, save=False)
            image.uploaded_by_user = request.user
            image.file_size = image.file.size
            image.file.open()
            image.file.seek(0)
            image._set_file_hash(image.file.read())
            image.file.seek(0)
            form.save()

            uploaded_image.file.delete()
            uploaded_image.delete()

            # Reindex the image to make sure all tags are indexed
            for backend in get_search_backends():
                backend.add(image)

            return JsonResponse({
                'success': True,
                'image_id': image.id,
            })
        else:
            return JsonResponse({
                'success': False,
                'form': render_to_string('wagtailimages/multiple/edit_form.html', {
                    'uploaded_image': uploaded_image,
                    'edit_action': reverse('wagtailimages:create_multiple_from_uploaded_image', args=(uploaded_image.id,)),
                    'delete_action': reverse('wagtailimages:delete_upload_multiple', args=(uploaded_image.id,)),
                    'form': form,
                }, request=request),
            })


class DeleteUploadView(View):
    http_method_names = ['post']

    def post(self, request, uploaded_image_id):
        uploaded_image = get_object_or_404(UploadedImage, id=uploaded_image_id)

        if not request.is_ajax():
            return HttpResponseBadRequest("Cannot POST to this view without AJAX")

        if uploaded_image.uploaded_by_user != request.user:
            raise PermissionDenied

        uploaded_image.file.delete()
        uploaded_image.delete()

        return JsonResponse({
            'success': True,
        })
