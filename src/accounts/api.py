from datetime import timedelta

from django.contrib.auth import get_user_model
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.shortcuts import get_object_or_404


from rest_framework import status, viewsets, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.permissions import IsAdminUser, AllowAny, IsAuthenticated
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from drf_yasg.utils import swagger_auto_schema

from accounts.models import (
    AdminInvitation,
    AdminProfile,
    ArtistProfile,
    CustomerProfile,
    UserVerificationRequest,
)
from core.exceptions import InvalidUserTypeError
from core.utils import encrypt_for_db

from .serializers import (
    AdminInvitationSerializer,
    AdminProfileSerializer,
    ArtisProfileDataSerializer,
    ArtisProfileDocumentSerializer,
    ArtistProfileSerializer,
    CustomerProfileSerializer,
    UserAccountDetailSerializer,
    UserDetailsTokenSerializer,
    CollectUserKYCDetailSerializer,
    UserLoginSerializer,
    UserCreateSerializer,
)

User = get_user_model()


class UserTokenResponseMixin:
    def get_user_token_response_data(self, user):
        refresh_token = RefreshToken.for_user(user)
        access_token = refresh_token.access_token
        access_token.set_exp(lifetime=timedelta(days=settings.WEB_TOKEN_EXPIRY))

        # if user.is_artist:
        #     user_profile = user.artistprofile_set

        # data = UserDetailsTokenSerializer(user_profile, context={"request": self.request}).data

        data = {
            "access_token": str(access_token),
            "refresh_token": str(refresh_token),
            "user": user,
        }

        return UserDetailsTokenSerializer(data, context={"request": self.request}).data


class UserRegistrationViewSet(viewsets.GenericViewSet, UserTokenResponseMixin, mixins.ListModelMixin):
    queryset = User.objects.all()
    serializer_class = UserCreateSerializer
    permission_classes = [AllowAny]


    def get_custom_serializer_class(self):
        user = self.request.user
        if user.is_artist:
            return ArtistProfileSerializer
        elif user.is_customer:
            return CustomerProfileSerializer
        elif user.is_admin:
            return AdminProfileSerializer

        raise InvalidUserTypeError()

    @csrf_exempt
    @action(methods=["post"], detail=False)
    @swagger_auto_schema(
        request_body=UserCreateSerializer,
        responses={200: UserDetailsTokenSerializer},
    )
    def signup(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "user": UserCreateSerializer(
                    user, context=self.get_serializer_context()
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(methods=["post"], detail=False)
    @swagger_auto_schema(
        request_body=UserLoginSerializer, responses={200: UserDetailsTokenSerializer}
    )
    @csrf_exempt
    def login(self, request, *args, **kwargs):
        serializer = UserLoginSerializer(
            data=request.data, context=self.get_serializer_context()
        )
        serializer.is_valid(raise_exception=True)

        user = serializer.save()
        data = self.get_user_token_response_data(user)

        data["is_artist"] = user.is_artist
        data["is_admin"] = user.is_admin
        data["is_customer"] = user.is_customer

        return Response(data)

    @action(methods=["put"], detail=False, permission_classes=[IsAuthenticated])
    @swagger_auto_schema(
        request_body=ArtisProfileDataSerializer, responses={200: ArtisProfileDataSerializer}
    )
    @transaction.atomic
    def update_artist_user_profile_data(self, request, *args, **kwargs):
        user_profile = self.get_user_profile(request.user)

        # Update the existing user profile with the new data
        serializer = ArtisProfileDataSerializer(
            instance=user_profile, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            data=ArtisProfileDataSerializer(instance=user_profile).data,
            status=status.HTTP_200_OK,
        )

    @action(methods=["put"], detail=False, permission_classes=[IsAuthenticated], parser_classes=[MultiPartParser])
    @swagger_auto_schema(
        request_body=ArtisProfileDocumentSerializer, responses={200: ArtisProfileDocumentSerializer}
    )
    @transaction.atomic
    def update_artist_user_profile_document(self, request, *args, **kwargs):
        user_profile = self.get_user_profile(request.user)

        # Update the existing user profile with the new data
        serializer = ArtisProfileDocumentSerializer(
            instance=user_profile, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            data=ArtisProfileDocumentSerializer(instance=user_profile).data,
            status=status.HTTP_200_OK,
        )
    
    @action(methods=["put"], detail=False, permission_classes=[IsAuthenticated],  parser_classes=[MultiPartParser])
    @swagger_auto_schema(
        request_body=CustomerProfileSerializer,
        responses={200: CustomerProfileSerializer},
    )
    @transaction.atomic
    def update_customer_user_profile(self, request, *args, **kwargs):
        user_profile = self.get_user_profile(request.user)

        # Update the existing user profile with the new data
        serializer = CustomerProfileSerializer(
            instance=user_profile, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            data=CustomerProfileSerializer(instance=user_profile).data,
            status=status.HTTP_200_OK,
        )

    @action(methods=["put"], detail=False, permission_classes=[IsAuthenticated])
    @swagger_auto_schema(
        request_body=AdminProfileSerializer, responses={200: AdminProfileSerializer}
    )
    @transaction.atomic
    def update_user_profile(self, request, *args, **kwargs):
        user_profile = self.get_user_profile(request.user)

        # Update the existing user profile with the new data
        serializer = AdminProfileSerializer(
            instance=user_profile, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            data=AdminProfileSerializer(instance=user_profile).data,
            status=status.HTTP_200_OK,
        )

    @swagger_auto_schema(
        responses={200: UserAccountDetailSerializer}
    )
    @action(methods=["get"], detail=True, permission_classes=[IsAuthenticated])
    def get_user_details(self, request, *args, **kwargs):
        user = self.get_object()
        serializer = UserAccountDetailSerializer(instance=user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def get_user_profile(self, user):
        if user.is_admin:
            return get_object_or_404(AdminProfile, user=user)
        elif user.is_customer:
            return get_object_or_404(CustomerProfile, user=user)
        elif user.is_artist:
            return get_object_or_404(ArtistProfile, user=user)
        else:
            raise InvalidUserTypeError

    @action(methods=["post"], detail=True, permission_classes=[IsAuthenticated])
    @swagger_auto_schema(
        request_body=CollectUserKYCDetailSerializer,
        responses={200: AdminProfileSerializer},
    )
    def update_user_kyc(self, request, *args, **kwargs):
        serializer = CollectUserKYCDetailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        bvn_data = data.pop("bvn")
        nin_data = data.pop("nin")

        user = self.get_object()

        bvn = encrypt_for_db(bvn_data)
        nin = encrypt_for_db(nin_data)

        # TODO: set up digital verification using a service like
        # QOREID after collection verification data
        UserVerificationRequest.objects.create(
            user=user,
            bvn=bvn,
            nin=nin,
            **data,
        )

        return Response("Verification request received")



class AdminInvitationViewSet(viewsets.ModelViewSet):
    queryset = AdminInvitation.objects.all()
    serializer_class = AdminInvitationSerializer
    permission_classes = [IsAdminUser]
